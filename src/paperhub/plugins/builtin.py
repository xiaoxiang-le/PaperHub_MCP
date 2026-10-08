from typing import Any

from paperhub.plugins.api import Outline, OutlineSection, PluginContext
from paperhub.plugins.manifest import PluginManifest

BUILTINS = {
    name: PluginManifest(
        name=name,
        version="0.1.0",
        entry="paperhub.plugins.builtin:SurveyOutlinePlugin",
        permissions=["read_library", "read_topics"],
        description=description,
    )
    for name, description in {
        "outline-survey": "按主题生成综述章节及文献建议（本地模板）",
        "outline-empirical": "生成 IMRaD 实验论文大纲（本地模板）",
        "outline-thesis": "生成学位论文大纲（本地模板）",
        "outline-from-draft": "从索引论文标题与主题建立草稿结构检查清单",
    }.items()
}


class SurveyOutlinePlugin:
    def generate(self, ctx: PluginContext, options: dict[str, Any]) -> Outline:
        citations = [paper["id"] for paper in ctx.papers]
        sections = [
            OutlineSection(
                title="引言 / Introduction",
                points=["定义研究范围与综述问题", "说明文献筛选标准"],
                citations=citations[:3],
            )
        ]
        if ctx.topics:
            for topic in ctx.topics:
                ids = [p for p in topic["paper_ids"] if p in citations]
                if ids:
                    sections.append(
                        OutlineSection(
                            title=topic["name"],
                            points=["比较研究方法、适用条件与评价指标", "阅读原文后归纳结论与局限"],
                            citations=ids,
                        )
                    )
        else:
            sections.append(
                OutlineSection(
                    title="研究方法与文献比较",
                    points=["按方法组织文献", "建立方法、数据集、结果对照表"],
                    citations=citations,
                )
            )
        sections.extend(
            [
                OutlineSection(
                    title="开放问题与未来方向", points=["根据证据辨析研究缺口"], citations=citations
                ),
                OutlineSection(
                    title="结论", points=["总结证据支持的结论与适用边界"], citations=citations[:3]
                ),
            ]
        )
        return Outline(
            title=options.get("title", "文献综述大纲"),
            sections=sections,
            notes=["本地模板大纲；引用为建议阅读项，不代表论文已支持该章节中的论断。"],
        )


def builtin_outline(name: str, ctx: PluginContext, options: dict[str, Any]) -> Outline:
    if name == "outline-survey":
        return SurveyOutlinePlugin().generate(ctx, options)
    titles = {
        "outline-empirical": ["Introduction", "Methods", "Results", "Discussion", "Conclusion"],
        "outline-thesis": ["绪论", "相关研究", "研究方法", "实验与结果", "讨论", "总结与展望"],
        "outline-from-draft": ["研究问题", "已有材料结构", "证据与引用检查", "逻辑缺口与补充计划"],
    }[name]
    return Outline(
        title=options.get("title", name),
        sections=[
            OutlineSection(
                title=title,
                points=["请基于实际研究材料补充本节论点和证据"],
                citations=[p["id"] for p in ctx.papers],
            )
            for title in titles
        ],
        notes=["这是可编辑的结构模板；不生成或推断实验结果。"],
    )
