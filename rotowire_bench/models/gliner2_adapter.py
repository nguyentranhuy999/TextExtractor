from __future__ import annotations

import copy
import re
import time
from collections import defaultdict
from pathlib import Path
from ..evaluation import norm
from ..schemas import Cell, Row, Table, TableOutput, gliner_schema
from ..utils import digest
from .common import ModelError


def split_text(text, fits, token_count, overlap_tokens=64):
    """Verbatim character windows; sentence ends preferred, word fallback explicit."""
    if not fits(""):
        raise ModelError("input_limit", "Schema consumes input budget")
    if fits(text):
        return [dict(start_char=0, end_char=len(text), text=text, overlap_tokens=0, boundary="document")]
    boundaries = sorted({m.end() for m in re.finditer(r"[.!?](?:[\"')\]]*)\s+", text)} | {len(text)})
    word_ends = [m.end() for m in re.finditer(r"\S+", text)]
    windows, start, covered = [], 0, 0
    while covered < len(text):
        candidates = [x for x in word_ends if x > covered]
        if not candidates:
            # Preserve terminal whitespace too.
            candidates = [len(text)]
        lo, hi, best = 0, len(candidates)-1, None
        while lo <= hi:
            mid = (lo+hi)//2
            if fits(text[start:candidates[mid]]):
                best = candidates[mid]
                lo = mid+1
            else:
                hi = mid-1
        if best is None:
            if start < covered:
                start = covered
                continue
            raise ModelError("input_limit", "No complete word fits after schema")
        preferred = [b for b in boundaries if covered < b <= best]
        end = max(preferred) if preferred else best
        overlap = token_count(text[start:covered]) if start < covered else 0
        windows.append(dict(start_char=start, end_char=end, text=text[start:end], overlap_tokens=overlap, boundary="sentence" if preferred else "word_fallback"))
        covered = end
        next_start = end
        # At most one quarter of this window's text budget; avoid one-word progress
        # when a large schema leaves little room. Fixed on validation, never gold-dependent.
        local_overlap_cap = min(overlap_tokens, token_count(text[start:end]) // 4)
        for candidate in sorted({m.start() for m in re.finditer(r"\S+", text[start:end])}):
            absolute = start+candidate
            if absolute > start and token_count(text[absolute:end]) <= local_overlap_cap:
                next_start = absolute
                break
        start = next_start
    return windows


def merge_chunks(raw_chunks, reverse):
    tables, duplicate_count, conflicts = [], 0, []
    for safe, (schema, mapping) in reverse.items():
        rows = {}
        for chunk_index, raw in enumerate(raw_chunks):
            for ri, record in enumerate(raw.get(safe, [])):
                def values(value):
                    vals = value if isinstance(value, list) else [value]
                    return [v.get("text", "") if isinstance(v,dict) else v for v in vals if v is not None]
                identity = values(record.get("entity_name"))
                name = identity[0] if identity and identity[0] else f"__unresolved_{safe}_{chunk_index}_{ri}"
                key = norm(name)
                row = rows.setdefault(key, {"name":name, "cells":defaultdict(list)})
                for f, name_f in mapping.items():
                    for value in values(record.get(f)):
                        if not value:
                            continue
                        if value in row["cells"][name_f]:
                            duplicate_count += 1
                        else:
                            row["cells"][name_f].append(value)
        output_rows = []
        for row in rows.values():
            cells = [Cell(field_name=f,raw_values=vs) for f,vs in row["cells"].items()]
            for cell in cells:
                if len(cell.raw_values)>1:
                    conflicts.append(dict(table=schema.table_name,entity=row["name"],**cell.model_dump()))
            output_rows.append(Row(entity_name=row["name"],cells=cells))
        tables.append(Table(table_name=schema.table_name,entity_type=schema.entity_type,field_names=[f.name for f in schema.fields],rows=output_rows))
    return TableOutput(tables=tables), {"duplicates_merged":duplicate_count,"conflicts":conflicts}


class GLiNER2Adapter:
    def __init__(self, config, *, local_files_only=False):
        import torch
        from gliner2 import GLiNER2
        self.config = config
        self.torch = torch
        torch.set_num_threads(config["cpu_threads"])
        torch.manual_seed(0)
        started = time.perf_counter_ns()
        revision = config["revision"]
        if not revision or not re.fullmatch(r"[a-f0-9]{40}",revision):
            raise ModelError("blocked", "GLiNER2 requires resolved checkpoint revision", attempted=False)
        local = Path(".cache/gliner2-base-v1") / revision
        if (local/"download_manifest.json").exists():
            from ..utils import read_json
            for entry in read_json(local/"download_manifest.json"):
                if digest((local/entry["filename"]).read_bytes()) != entry["sha256"]:
                    raise ModelError("blocked", "Checkpoint integrity failure", attempted=False)
            path = str(local)
        else:
            from huggingface_hub import snapshot_download
            path = snapshot_download(config["model"],revision=revision,cache_dir=config["cache_dir"],local_files_only=local_files_only,
                                     allow_patterns=["*.json","*.model","*.safetensors"])
        self.model = GLiNER2.from_pretrained(path).to(device=config["device"],dtype=torch.float32).eval()
        self.model.processor.change_mode(is_training=False)
        self.max_length = self.model.encoder.config.max_position_embeddings
        self.max_records = [m.out_features for m in self.model.count_pred.modules() if isinstance(m,torch.nn.Linear)][-1]-1
        self.tokenizer = self.model.processor.tokenizer
        self.load_ms = (time.perf_counter_ns()-started)/1e6
        self.saturation_counts = []
        self.model.count_pred.register_forward_hook(lambda module,args,out:self.saturation_counts.extend(out.argmax(dim=-1).detach().cpu().tolist()))
        warm = self.model.create_schema().structure("person").field("name",dtype="str",description="Person name").field("value",dtype="list",description="Reported value")
        self.sync()
        start = time.perf_counter_ns()
        with torch.inference_mode():
            self.model.extract("Alex recorded seven. Jamie recorded three.",warm,threshold=config["threshold"])
        self.sync()
        self.warmup_ms = (time.perf_counter_ns()-start)/1e6
        self.metadata = dict(model=config["model"],revision=revision,torch_seed=0,max_input_tokens=self.max_length,
            max_span_words=self.model.max_width,max_records_per_type=self.max_records,
            table_field_limit="No separate static limit observed in gliner2 1.2.4; all schema tokens must fit input budget",
            threshold=config["threshold"],count_decoder="argmax over 0..19; no confidence threshold",
            load_ms=self.load_ms,warmup_ms=self.warmup_ms,device=config["device"],dtype=config["dtype"],cpu_threads=config["cpu_threads"],
            cuda_version=torch.version.cuda,gpu=torch.cuda.get_device_name() if config["device"].startswith("cuda") else None)

    def sync(self):
        if self.config["device"].startswith("cuda"):
            self.torch.cuda.synchronize()

    def extract(self, item, schema, emit):
        if not schema.tables:
            return TableOutput(tables=[])
        from ..schemas import ExtractionSchema
        mode = self.config.get("table_execution", "joint")
        if mode not in ("joint", "separate"):
            raise ValueError("Unknown GLiNER table execution mode")
        groups = [schema] if mode == "joint" else [ExtractionSchema(tables=[t]) for t in schema.tables]
        plans, all_chunks = [], []
        processor = self.model.processor
        def count(text):
            return sum(len(self.tokenizer.tokenize(word)) for word in processor._tokenize_text(text))
        for group_index, group in enumerate(groups):
            builder, reverse = gliner_schema(group,self.model,
                labels=self.config.get("schema_labels", "semantic"),
                descriptions=self.config.get("schema_descriptions", "full"))
            built = builder.build()
            def fits(text):
                adjusted = text if text.endswith((".","!","?")) else text+"."
                record = processor.transform_and_format(adjusted,copy.deepcopy(built))
                if record.num_schemas != len(group.tables):
                    raise ModelError("input_limit","Processor dropped schema entries")
                return len(record.input_ids) <= self.max_length
            chunks = split_text(item.full_text,fits,count,self.config["overlap_tokens"])
            chunks = [dict(c, group_index=group_index) for c in chunks]
            plans.append((builder, reverse, built, chunks))
            all_chunks.extend(chunks)
        # Plan all groups before inference. No partial success if any schema
        # cannot fit; every group's full source text is covered independently.
        emit("gliner_request",dict(schema=schema.model_dump(),
            adapted_schema=plans[0][2] if len(plans)==1 else [p[2] for p in plans],
            table_execution=mode,chunks=all_chunks))
        tables, duplicate_count, conflicts, index = [], 0, [], 0
        for builder, reverse, built, chunks in plans:
            results = []
            for chunk in chunks:
                self.sync()
                started = time.perf_counter_ns()
                self.saturation_counts.clear()
                with self.torch.inference_mode():
                    raw = self.model.extract(chunk["text"],builder,threshold=self.config["threshold"],format_results=False,include_spans=True,include_confidence=True)
                self.sync()
                results.append(raw)
                emit("gliner_chunk",dict(index=index,**chunk,raw=raw,duration_ms=(time.perf_counter_ns()-started)/1e6,
                     predicted_counts=list(self.saturation_counts),suspected_saturation=any(c>=self.max_records for c in self.saturation_counts)))
                index += 1
            output, metadata = merge_chunks(results,reverse)
            tables.extend(output.tables)
            duplicate_count += metadata["duplicates_merged"]
            conflicts.extend(metadata["conflicts"])
        emit("gliner_merge",dict(duplicates_merged=duplicate_count,conflicts=conflicts))
        return TableOutput(tables=tables)
