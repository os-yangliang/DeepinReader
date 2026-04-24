import re
from typing import List

from services.paper_schema import PaperSection, SectionType


SECTION_PATTERNS = [
    (re.compile(r"^(abstract|摘要)\s*$", re.I), SectionType.ABSTRACT),
    (re.compile(r"^(introduction|引言)\s*$", re.I), SectionType.INTRODUCTION),
    (re.compile(r"^(related work|background|相关工作)\s*$", re.I), SectionType.RELATED_WORK),
    (re.compile(r"^(method|approach|methodology|模型|方法)\s*$", re.I), SectionType.METHOD),
    (re.compile(r"^(experiment|experiments|experimental setup|实验|实验设置)\s*$", re.I), SectionType.EXPERIMENT),
    (re.compile(r"^(result|results|实验结果|结果)\s*$", re.I), SectionType.RESULT),
    (re.compile(r"^(ablation|ablation study|消融实验)\s*$", re.I), SectionType.ABLATION),
    (re.compile(r"^(conclusion|conclusions|结论)\s*$", re.I), SectionType.CONCLUSION),
    (re.compile(r"^(limitation|limitations|局限性)\s*$", re.I), SectionType.LIMITATION),
    (re.compile(r"^(appendix|附录)\s*$", re.I), SectionType.APPENDIX),
]

NUMBERED_HEADING = re.compile(r"^(\d+(?:\.\d+)*)\s+(.+)$")


class SectionParser:
    def parse(self, text: str) -> List[PaperSection]:
        lines = text.splitlines()
        sections: List[PaperSection] = []
        current_title = "全文"
        current_type = SectionType.OTHER
        current_level = 1
        buffer: List[str] = []
        start_line = 1
        section_idx = 1

        def flush(end_line: int):
            nonlocal section_idx, buffer, start_line, current_title, current_type, current_level
            content = "\n".join(buffer).strip()
            if content:
                sections.append(PaperSection(
                    section_id=f"sec_{section_idx}",
                    title=current_title,
                    level=current_level,
                    section_type=current_type,
                    content=content,
                    start_line=start_line,
                    end_line=end_line,
                ))
                section_idx += 1
            buffer = []

        for idx, raw_line in enumerate(lines, start=1):
            line = raw_line.strip()
            detected = self._detect_heading(line)
            if detected:
                if buffer:
                    flush(idx - 1)
                current_title, current_type, current_level = detected
                start_line = idx
            else:
                buffer.append(raw_line)

        if buffer:
            flush(len(lines))

        if not sections:
            sections.append(PaperSection(
                section_id="sec_1",
                title="全文",
                level=1,
                section_type=SectionType.OTHER,
                content=text.strip(),
                start_line=1,
                end_line=len(lines),
            ))
        return sections

    def _detect_heading(self, line: str):
        if not line or len(line) > 120:
            return None

        numbered = NUMBERED_HEADING.match(line)
        candidate = numbered.group(2).strip() if numbered else line
        level = len(numbered.group(1).split(".")) if numbered else 1

        for pattern, section_type in SECTION_PATTERNS:
            if pattern.match(candidate):
                return candidate, section_type, level

        if numbered and candidate[:1].isupper() and len(candidate.split()) <= 8:
            return candidate, SectionType.OTHER, level

        return None
