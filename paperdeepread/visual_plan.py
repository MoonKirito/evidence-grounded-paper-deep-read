"""Choose nonredundant method coverage and an explicit experimental proof chain."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

from paperdeepread.providers.base import ChatMessage, ModelClient
from paperdeepread.utils import SKILL_DIR
from paperdeepread.visuals import parse_json_response

spec = importlib.util.spec_from_file_location("visual_contract", SKILL_DIR / "scripts" / "visual_contract.py")
contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)

PLAN_INSTRUCTIONS = """根据已完成的全部实图预读，先形成全局选图与贡献证据覆盖计划，暂时不要写正文。
How：技术路线、整体架构、关键模块、训练/推理流程及机制示意图，去重后应尽量全部展示讲解。
同一模块不等于同一信息：总流程图与局部机制图通常互补，应同时保留。
只有另一张图完整覆盖了该图的技术信息时才能以 duplicate_of 去重，并写明具体重合内容和保留代表。
同一技术信息在 covers 中使用完全相同的名称；被去重图的 covers 必须是代表图 covers 的子集，不能遗漏独特技术信息。
不能仅因篇幅、附录来源或单图 selected=false 就省略独立的方法图；不可读/提取失败须明确限制。
Experiment：先区分论文核心贡献的直接证据与辅助诊断，按论文目标建立证明链，自主选择图表，不凑数量。
效果、泛化、标注效率等核心贡献各自检查；每条实验证明链优先选择一个最能说明结果与边界的代表图表。
不同视角、粒度、参数检查不自动构成独立核心贡献。冻结/微调等确有不同结论的设置可以分别展示。
同一证明链追加第二张图表，必须说明新增信息为何对判断核心结论不可缺少、为何不能用一两句准确文字承载。
训练诊断、层选择、采样敏感性、逐受试者明细、探索性分析的补充视角通常用文字引用；若支撑关键质疑或核心结论才展示。
不要逐张把“有新信息”当成必须展示；不要为了覆盖分析记录而接近全量插入实验图。
也不能把多条独立核心证明链笼统以“简洁”为由全部改成文字；仅文字呈现需具体理由。
逐项决定所有图表，含不展示项目。section 原来为 how 且可读的图只能在 how 中 include=true，
或指向另一张已选 how 图作为 duplicate_of。图表不能凭空改路径。
只输出 JSON 对象：
{
 "items": [{"id":"Figure 1","image":"extracted/figures/xxx.png","section":"how",
            "include":true,"duplicate_of":"","covers":["输入→预训练→下游输出"],"reason":"具体选择理由"}],
 "claims": [{"claim":"一项核心贡献或设计目标","evidence":["Sec. 3, Fig. 4"],
             "visuals":["Figure 4"],"presentation":"image","reason":"为何需要展示或为何文字足够"}]
}
section 取 what/why/how/experiment/question/none。id 必须为 manifest 的 figType + 空格 + name。
include=false 也必须写 reason；duplicate_of 使用代表图 id，非重复时为空字符串。
claims 覆盖论文核心贡献，不只列平均准确率；presentation 取 image/text，image 必须有已选图支持。
"""


def build_visual_plan(extracted_dir: Path, client: ModelClient, language: str) -> Path:
    analysis_path = extracted_dir / "visual_analysis.json"
    analysis = json.loads(analysis_path.read_text(encoding="utf-8-sig"))
    if not analysis.get("complete"):
        raise RuntimeError("Complete all-visual analysis before global visual planning.")
    paper_text = (extracted_dir / "full_text.md").read_text(encoding="utf-8-sig")[:36000]
    context = json.dumps(analysis, ensure_ascii=False)
    fingerprint = hashlib.sha256((PLAN_INSTRUCTIONS + language + repr(client.config) + paper_text + context).encode("utf-8")).hexdigest()
    output = extracted_dir / "visual_plan.json"
    if output.exists():
        cached = json.loads(output.read_text(encoding="utf-8"))
        if cached.get("fingerprint") == fingerprint and cached.get("complete") and not contract.plan_problems(cached, analysis):
            return output
        output.unlink()
    messages = [ChatMessage("system", PLAN_INSTRUCTIONS),
                ChatMessage("user", f"计划语言：{language}\n# Paper Text\n{paper_text}\n# All Visual Analyses\n{context}")]
    plan = parse_json_response(client.complete(messages))
    problems = contract.plan_problems(plan, analysis)
    if problems:
        # One bounded schema/coverage repair, before any report writing starts.
        messages.extend([ChatMessage("assistant", json.dumps(plan, ensure_ascii=False)),
                         ChatMessage("user", "请修正以下计划问题，只输出完整 JSON；不得丢弃独立方法图：\n" + "\n".join(problems))])
        plan = parse_json_response(client.complete(messages))
        problems = contract.plan_problems(plan, analysis)
    if problems:
        raise RuntimeError("Invalid visual plan: " + "; ".join(problems))
    plan.update(complete=True, fingerprint=fingerprint)
    output.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return output
