#!/usr/bin/env python3
"""Build the runtime catalog for the PEP 2024 grade-7 upper textbook.

The Markdown files and PDF in docs/books remain the source of truth. This script
creates compact, deployable JSON plus visually faithful activity-page crops.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path

from PIL import Image
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
BOOKS = ROOT / "docs" / "books"
OUTPUT_ROOT = ROOT / "src" / "classroom" / "assets" / "pep_grade7_upper_2024"
CATALOG_PATH = OUTPUT_ROOT / "catalog.json"
EXERCISE_ROOT = OUTPUT_ROOT / "exercises"
PDF_PATH = BOOKS / "（根据2022年版课程标准修订）义务教育教科书 英语 七年级 上册.pdf"
CORE_PATH = BOOKS / "七年级上册-分单元词汇表.md"
PRIMARY_PATH = BOOKS / "七年级上册-Vocabulary-from-Primary-School.md"
TEACHING_PATH = BOOKS / "七年级上册-分单元教学内容解析.md"

UNIT_SPECS = (
    (1, "Starter Unit 1", "Hello!", 1, 6),
    (2, "Starter Unit 2", "Keep Tidy!", 7, 12),
    (3, "Starter Unit 3", "Welcome!", 13, 18),
    (4, "Unit 1", "You and Me", 19, 26),
    (5, "Unit 2", "We’re Family!", 27, 34),
    (6, "Unit 3", "My School", 35, 42),
    (7, "Unit 4", "My Favourite Subject", 43, 50),
    (8, "Unit 5", "Fun Clubs", 51, 58),
    (9, "Unit 6", "A Day in the Life", 59, 66),
    (10, "Unit 7", "Happy Birthday!", 67, 74),
)

# The teaching-analysis Markdown defines each unit's language scope. These small
# deterministic lesson packs turn that scope into explicit, assessable grammar
# learning instead of asking the LLM to invent rules or answer keys.
GRAMMAR_LABS: dict[int, dict[str, object]] = {
    1: {
        "title": "用合适的问候开启并结束对话",
        "can_do": "我能根据时间和交际阶段选择问候语，并完成“问候—姓名—近况—告别”。",
        "rule": "问候语不是随便互换：时间、初次见面和结束对话分别有常用表达。姓名和句首要大写。",
        "forms": ["早晨：Good morning.", "初次见面：Nice to meet you.", "结束：Goodbye. / See you."],
        "examples": [
            {"en": "Good morning. I'm Emma.", "zh": "早上好。我是埃玛。"},
            {"en": "Nice to meet you, Emma.", "zh": "很高兴认识你，埃玛。"},
        ],
        "common_error": "见面时只会反复说 Hello，或者把人名写成小写。",
        "checks": [
            {"id": "g1", "prompt": "早晨第一次见到老师，最合适的是？", "options": ["Good morning.", "Goodbye.", "Good night."], "answer": "Good morning.", "explanation": "Good morning 用于上午见面问候。"},
            {"id": "g2", "prompt": "对方说 Nice to meet you.，你应回答？", "options": ["Nice to meet you too.", "I'm fine.", "See you."], "answer": "Nice to meet you too.", "explanation": "too 表示“我也很高兴认识你”。"},
            {"id": "g3", "prompt": "哪一句大小写正确？", "options": ["My name is Peter.", "my name is peter.", "My Name Is peter."], "answer": "My name is Peter.", "explanation": "句首和人名首字母大写。"},
        ],
        "transfer_prompt": "写一个含问候、姓名和告别的 3 句迷你对话。",
    },
    2: {
        "title": "用 it/they 和 in/on/under 描述物品",
        "can_do": "我能根据单复数选择 is/are，并说明一个或多个物品的颜色和位置。",
        "rule": "单数物品用 it + is，复数物品用 they + are；位置用 in、on、under。",
        "forms": ["What colour is it? It is blue.", "What colour are they? They are black.", "It is under the desk."],
        "examples": [
            {"en": "The cap is red. It is on the chair.", "zh": "帽子是红色的，在椅子上。"},
            {"en": "The shoes are black. They are under the bed.", "zh": "鞋是黑色的，在床下。"},
        ],
        "common_error": "看到 shoes、glasses 仍使用 it is，或把 colour 写成 colours。",
        "checks": [
            {"id": "g1", "prompt": "The shoes ___ black.", "options": ["is", "are", "am"], "answer": "are", "explanation": "shoes 是复数，be 动词用 are。"},
            {"id": "g2", "prompt": "书在书包里面，应使用？", "options": ["in", "on", "under"], "answer": "in", "explanation": "in 表示在某物内部。"},
            {"id": "g3", "prompt": "询问一顶帽子的颜色，应说？", "options": ["What colour is it?", "What colour are they?", "What colours is it?"], "answer": "What colour is it?", "explanation": "单数用 it/is，What colour 中 colour 不加复数。"},
        ],
        "transfer_prompt": "用两句话描述你身边一个物品的颜色和位置。",
    },
    3: {
        "title": "用 this/that/these/those 指认事物",
        "can_do": "我能同时判断远近和单复数，并用 How many 询问数量。",
        "rule": "近处单数 this，远处单数 that；近处复数 these，远处复数 those。How many 后接可数名词复数。",
        "forms": ["What's this/that? It's ...", "What are these/those? They're ...", "How many rabbits can you see?"],
        "examples": [
            {"en": "What's that? It's a goose.", "zh": "远处那个是什么？是一只鹅。"},
            {"en": "What are these? They're carrots.", "zh": "近处这些是什么？是胡萝卜。"},
        ],
        "common_error": "只看远近、不看单复数；How many 后仍用单数名词。",
        "checks": [
            {"id": "g1", "prompt": "指着手边的两只兔子，应说？", "options": ["these rabbits", "this rabbit", "those rabbits"], "answer": "these rabbits", "explanation": "近处复数用 these。"},
            {"id": "g2", "prompt": "What's that? 的正确回答是？", "options": ["It's a cow.", "They're cows.", "This is cows."], "answer": "It's a cow.", "explanation": "that 是单数，回答用 it is。"},
            {"id": "g3", "prompt": "哪一句正确？", "options": ["How many sheep can you see?", "How many sheepes can you see?", "How much sheep can you see?"], "answer": "How many sheep can you see?", "explanation": "sheep 单复数同形，数量询问用 How many。"},
        ],
        "transfer_prompt": "想象一个农场，用 this/that/these/those 和 How many 各写一句。",
    },
    4: {
        "title": "be 动词随主语变化",
        "can_do": "我能用 am/is/are 连续询问并介绍姓名、年龄、国家和班级。",
        "rule": "I 搭配 am；he/she/it 和单数名词搭配 is；you/we/they 和复数名词搭配 are。",
        "forms": ["I am 13 years old.", "She is from Singapore.", "They are classmates."],
        "examples": [
            {"en": "I'm Peter. I'm from the UK.", "zh": "我是彼得，来自英国。"},
            {"en": "Where is she from? She is from China.", "zh": "她来自哪里？她来自中国。"},
        ],
        "common_error": "I 后用 is，或第三人称单数与 are 搭配。",
        "checks": [
            {"id": "g1", "prompt": "I ___ in Class 1.", "options": ["am", "is", "are"], "answer": "am", "explanation": "I 固定搭配 am。"},
            {"id": "g2", "prompt": "Emma and Peter ___ classmates.", "options": ["is", "are", "am"], "answer": "are", "explanation": "两个人构成复数主语，用 are。"},
            {"id": "g3", "prompt": "询问她来自哪里，应说？", "options": ["Where is she from?", "Where are she from?", "Where she is from?"], "answer": "Where is she from?", "explanation": "特殊疑问句中 be 动词放在主语前。"},
        ],
        "transfer_prompt": "用 3 句话介绍自己，再用 1 句话介绍一位同学。",
    },
    5: {
        "title": "一般现在时第三人称单数与所有格",
        "can_do": "我能介绍家人的关系、爱好和特点，并用 ’s 表示所属。",
        "rule": "he/she/单个人名作主语时，一般现在时动词通常加 -s/-es；名词 + ’s 表示“某人的”。",
        "forms": ["My father likes sports.", "Emma has a brother.", "This is Peter's family."],
        "examples": [
            {"en": "My sister plays the piano.", "zh": "我姐姐弹钢琴。"},
            {"en": "This is my grandparents' dog.", "zh": "这是我祖父母的狗。"},
        ],
        "common_error": "he/she 后仍用动词原形，或遗漏所有格撇号。",
        "checks": [
            {"id": "g1", "prompt": "My brother ___ football.", "options": ["likes", "like", "liking"], "answer": "likes", "explanation": "My brother 是第三人称单数，like 加 -s。"},
            {"id": "g2", "prompt": "She ___ two cousins.", "options": ["has", "have", "haves"], "answer": "has", "explanation": "have 的第三人称单数是 has。"},
            {"id": "g3", "prompt": "“彼得的妹妹”应写作？", "options": ["Peter's sister", "Peters sister", "Peter sister's"], "answer": "Peter's sister", "explanation": "人名后加 ’s 表示所属。"},
        ],
        "transfer_prompt": "用 3 句话介绍一位家人，至少使用一个第三人称单数动词和一个所有格。",
    },
    6: {
        "title": "there be 与 have 不混用",
        "can_do": "我能说明学校有什么、在哪里，并区分“某处存在”和“某人拥有”。",
        "rule": "there be 表示某处有某物，be 与后面紧邻的名词一致；have/has 表示某人或某物拥有。",
        "forms": ["There is a library next to the hall.", "There are two buildings.", "Our school has a large playground."],
        "examples": [
            {"en": "There are some trees behind the library.", "zh": "图书馆后面有一些树。"},
            {"en": "Our classroom has a reading corner.", "zh": "我们的教室有一个阅读角。"},
        ],
        "common_error": "写成 There have，或忽略离 be 最近名词的单复数。",
        "checks": [
            {"id": "g1", "prompt": "___ a gym in our school.", "options": ["There is", "There are", "There have"], "answer": "There is", "explanation": "a gym 是单数，使用 There is。"},
            {"id": "g2", "prompt": "Our school ___ two science labs.", "options": ["has", "there are", "have"], "answer": "has", "explanation": "主语 Our school 表示拥有，用 has。"},
            {"id": "g3", "prompt": "餐厅在体育馆旁边，应使用哪个介词短语？", "options": ["next to", "between", "under"], "answer": "next to", "explanation": "next to 表示紧邻、在旁边。"},
        ],
        "transfer_prompt": "用 there be 和 have/has 各写一句介绍你的学校。",
    },
    7: {
        "title": "用 why/because 说明学科偏好",
        "can_do": "我能说出喜欢或不喜欢的学科，并给出具体理由。",
        "rule": "Why ...? 询问原因，回答用 Because + 完整原因；and 补充同向信息，but 表示转折。",
        "forms": ["Why do you like science?", "Because it helps me understand the world.", "Maths is difficult, but it is useful."],
        "examples": [
            {"en": "I like history because I learn about the past.", "zh": "我喜欢历史，因为我了解过去。"},
            {"en": "Art is relaxing, and it helps me be creative.", "zh": "美术让人放松，也帮助我发挥创造力。"},
        ],
        "common_error": "用 Because 单独回答却没有具体理由，或 because 与 so 同时使用。",
        "checks": [
            {"id": "g1", "prompt": "___ do you like English?", "options": ["Why", "What", "When"], "answer": "Why", "explanation": "询问原因用 Why。"},
            {"id": "g2", "prompt": "I like IT ___ I can learn useful skills.", "options": ["because", "but", "so because"], "answer": "because", "explanation": "because 引出原因。"},
            {"id": "g3", "prompt": "Maths is difficult, ___ I want to improve it.", "options": ["but", "because", "and because"], "answer": "but", "explanation": "前后意义转折，用 but。"},
        ],
        "transfer_prompt": "选择一门学科，用“评价 + because 理由”写两句话，理由不能只写 fun。",
    },
    8: {
        "title": "can/can’t 后使用动词原形",
        "can_do": "我能谈论自己会做和不会做的事，并询问他人的能力。",
        "rule": "can 后直接接动词原形，不随主语变化；否定用 can’t；一般疑问句把 can 放到主语前。",
        "forms": ["I can play chess.", "She can't dance.", "Can you play an instrument?"],
        "examples": [
            {"en": "He can play the guitar, but he can't sing.", "zh": "他会弹吉他，但不会唱歌。"},
            {"en": "Can Emma swim? Yes, she can.", "zh": "埃玛会游泳吗？是的，她会。"},
        ],
        "common_error": "can 后加 -s 或 to，例如 can plays、can to dance。",
        "checks": [
            {"id": "g1", "prompt": "She can ___ very well.", "options": ["dance", "dances", "to dance"], "answer": "dance", "explanation": "can 后使用动词原形。"},
            {"id": "g2", "prompt": "把 He can swim. 变成一般疑问句。", "options": ["Can he swim?", "Does he can swim?", "Can he swims?"], "answer": "Can he swim?", "explanation": "can 提到主语前，动词仍用原形。"},
            {"id": "g3", "prompt": "否定“我不会弹吉他”应说？", "options": ["I can't play the guitar.", "I don't can play the guitar.", "I can't plays the guitar."], "answer": "I can't play the guitar.", "explanation": "can 的否定是 can't，后接原形 play。"},
        ],
        "transfer_prompt": "写 3 句话：一件你会做的事、一件不会做的事、一个询问同学能力的问题。",
    },
    9: {
        "title": "准确表达时间与日常作息",
        "can_do": "我能询问具体钟点和较宽泛的时间，并用第三人称描述一天。",
        "rule": "What time 常问具体钟点，When 可问更宽泛的时间；he/she 的日常动作通常用第三人称单数。",
        "forms": ["What time do you get up?", "When do you exercise?", "He goes to school at 7:30."],
        "examples": [
            {"en": "I have breakfast at half past seven.", "zh": "我七点半吃早餐。"},
            {"en": "She usually finishes school at five.", "zh": "她通常五点放学。"},
        ],
        "common_error": "具体钟点前漏掉 at，或 she/he 后仍用 go、have 等原形。",
        "checks": [
            {"id": "g1", "prompt": "询问“你几点起床”最准确的是？", "options": ["What time do you get up?", "Where do you get up?", "How much do you get up?"], "answer": "What time do you get up?", "explanation": "具体钟点用 What time。"},
            {"id": "g2", "prompt": "He ___ to school at 7:30.", "options": ["goes", "go", "going"], "answer": "goes", "explanation": "He 是第三人称单数，go 变为 goes。"},
            {"id": "g3", "prompt": "She has lunch ___ twelve.", "options": ["at", "on", "in"], "answer": "at", "explanation": "具体钟点前使用 at。"},
        ],
        "transfer_prompt": "按时间顺序写 3 句你的作息，再把其中一句改成 he/she 主语。",
    },
    10: {
        "title": "日期、数量与购物问答",
        "can_do": "我能说生日日期，在购物时询问价格和数量。",
        "rule": "日期用序数词，具体日期前用 on；How much 问价格或不可数数量，How many 问可数名词数量。",
        "forms": ["My birthday is on May 2nd.", "How much is the cake?", "How many candles do we need?"],
        "examples": [
            {"en": "Her birthday is on the twenty-first of June.", "zh": "她的生日是六月二十一日。"},
            {"en": "How much are the flowers? They're 30 yuan.", "zh": "这些花多少钱？30元。"},
        ],
        "common_error": "日期使用基数词、具体日期前用 in，或用 How much 询问可数数量。",
        "checks": [
            {"id": "g1", "prompt": "“在五月二日”应写作？", "options": ["on May 2nd", "in May 2", "at May 2nd"], "answer": "on May 2nd", "explanation": "具体日期前用 on，日期使用序数词。"},
            {"id": "g2", "prompt": "询问蛋糕价格，应说？", "options": ["How much is the cake?", "How many is the cake?", "What much is the cake?"], "answer": "How much is the cake?", "explanation": "询问价格使用 How much。"},
            {"id": "g3", "prompt": "询问需要多少支蜡烛，应说？", "options": ["How many candles do we need?", "How much candles do we need?", "How old candles do we need?"], "answer": "How many candles do we need?", "explanation": "candles 是可数名词复数，用 How many。"},
        ],
        "transfer_prompt": "写出你的生日日期，再写一组购物问答（商品和价格）。",
    },
}

UNIT_HEADING = re.compile(r"^## ((?:Starter )?Unit \d+)\s+(.+?)\s*$")
PDF_READER = PdfReader(PDF_PATH)


def _unit_key(title: str, subtitle: str) -> str:
    return f"{title} {subtitle}".replace("'", "’").strip()


def _table_cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def parse_core_vocabulary() -> dict[str, list[dict[str, object]]]:
    result: dict[str, list[dict[str, object]]] = {}
    current: str | None = None
    section = "core"
    for line in CORE_PATH.read_text(encoding="utf-8").splitlines():
        match = UNIT_HEADING.match(line)
        if match:
            current = _unit_key(match.group(1), match.group(2))
            result[current] = []
            section = "core"
            continue
        if line.startswith("### "):
            section = "proper_noun" if any(token in line for token in ("人名", "专有", "地名")) else "core"
            continue
        if not current or not line.startswith("|") or line.startswith("|---"):
            continue
        cells = _table_cells(line)
        if not cells or cells[0] in {"单词或短语", "名称"}:
            continue
        if len(cells) == 5:
            term, phonetic, part_of_speech, meaning, page = cells
        elif len(cells) == 4:
            term, phonetic, meaning, page = cells
            part_of_speech = "proper noun"
        else:
            continue
        page_match = re.search(r"\d+", page)
        result[current].append(
            {
                "term": term,
                "phonetic": None if phonetic in {"", "-", "—"} else phonetic,
                "part_of_speech": part_of_speech,
                "meaning_zh": meaning,
                "printed_page": int(page_match.group()) if page_match else None,
                "band": section,
            }
        )
    return result


def parse_primary_vocabulary() -> dict[str, list[dict[str, object]]]:
    result: dict[str, list[dict[str, object]]] = {}
    current: str | None = None
    for line in PRIMARY_PATH.read_text(encoding="utf-8").splitlines():
        match = UNIT_HEADING.match(line)
        if match:
            current = _unit_key(match.group(1), match.group(2))
            result[current] = []
            continue
        if not current or not line.startswith("|") or line.startswith("|---"):
            continue
        cells = _table_cells(line)
        if len(cells) != 4 or cells[0] == "单词":
            continue
        for offset in (0, 2):
            term, meaning = cells[offset : offset + 2]
            if term:
                result[current].append(
                    {
                        "term": term,
                        "phonetic": None,
                        "part_of_speech": None,
                        "meaning_zh": meaning,
                        "printed_page": None,
                        "band": "primary_review",
                    }
                )
    return result


def parse_teaching_sections() -> dict[str, dict[str, list[str]]]:
    result: dict[str, dict[str, list[str]]] = {}
    current: str | None = None
    subsection = "overview"
    for raw_line in TEACHING_PATH.read_text(encoding="utf-8").splitlines():
        match = UNIT_HEADING.match(raw_line)
        if match:
            current = _unit_key(match.group(1), match.group(2))
            result[current] = {"overview": []}
            subsection = "overview"
            continue
        if current and raw_line.startswith("## "):
            current = None
            continue
        if not current:
            continue
        if raw_line.startswith("### "):
            subsection = raw_line.removeprefix("### ").strip()
            result[current].setdefault(subsection, [])
            continue
        line = raw_line.strip()
        if not line or line.startswith("|---"):
            continue
        if line.startswith(("- ", "* ")):
            line = line[2:].strip()
        result[current].setdefault(subsection, []).append(line)
    return result


def _render_activity_crop(*, printed_page: int, destination: Path) -> None:
    pdf_page = printed_page + 9
    with tempfile.TemporaryDirectory(prefix="binnagent-grade7-") as temp_dir:
        prefix = Path(temp_dir) / "page"
        subprocess.run(
            [
                "pdftoppm", "-f", str(pdf_page), "-l", str(pdf_page), "-r", "132",
                "-singlefile", "-png", str(PDF_PATH), str(prefix),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        with Image.open(prefix.with_suffix(".png")) as image:
            width, height = image.size
            crop = image.crop((int(width * 0.045), int(height * 0.055), int(width * 0.955), int(height * 0.94)))
            destination.parent.mkdir(parents=True, exist_ok=True)
            crop.save(destination, "WEBP", quality=88, method=6)


def _extract_page_text(*, printed_page: int) -> str:
    pdf_page = printed_page + 9
    text = PDF_READER.pages[pdf_page - 1].extract_text() or ""
    return re.sub(r"[ \t]+", " ", text).strip()


def _page_task_copy(source_text: str) -> tuple[str, str, str]:
    if "In this unit, you will" in source_text:
        return (
            "launch",
            "单元导学页",
            "阅读 BIG Question 和本单元学习产出，写下你最想解决的一个问题。",
        )
    if "Project" in source_text:
        return (
            "project",
            "Project 综合任务",
            "按教材步骤完成项目产出；先写草稿，再让 AI 检查是否覆盖任务要求。",
        )
    if "Pronunciation" in source_text:
        return (
            "pronunciation",
            "Pronunciation 听辨任务",
            "先播放本单元原声，再完成页面中的听辨、圈选或朗读辨音活动。",
        )
    if "SECTION B" in source_text or "Section B" in source_text:
        return (
            "section_b",
            "Section B 教材任务",
            "阅读教材语篇并按活动编号完成理解、表达或写作任务。",
        )
    return (
        "section_a",
        "Section A 教材任务",
        "查看教材原题，按活动编号完成选择、填空、听力或对话任务。遇到听力标识时先播放本单元原声。",
    )


def build_catalog() -> dict[str, object]:
    core = parse_core_vocabulary()
    primary = parse_primary_vocabulary()
    teaching = parse_teaching_sections()
    units: list[dict[str, object]] = []
    EXERCISE_ROOT.mkdir(parents=True, exist_ok=True)
    for old_asset in EXERCISE_ROOT.glob("*.webp"):
        old_asset.unlink()
    for ordinal, title, subtitle, page_start, page_end in UNIT_SPECS:
        key = _unit_key(title, subtitle)
        slug = re.sub(r"[^a-z0-9]+", "-", f"{title}-{subtitle}".casefold()).strip("-")
        tasks = []
        for printed_page in range(page_start, page_end + 1):
            source_text = _extract_page_text(printed_page=printed_page)
            task_kind, task_title, instruction = _page_task_copy(source_text)
            filename = f"{ordinal:02d}-{slug}-p{printed_page}.webp"
            _render_activity_crop(printed_page=printed_page, destination=EXERCISE_ROOT / filename)
            tasks.append(
                {
                    "id": f"unit-{ordinal}-page-{printed_page}",
                    "kind": task_kind,
                    "title": task_title,
                    "instruction": instruction,
                    "asset": filename,
                    "printed_page": printed_page,
                    "pdf_page": printed_page + 9,
                    "source_text": source_text,
                    "response_type": "text",
                }
            )
        units.append(
            {
                "ordinal": ordinal,
                "title": title,
                "subtitle": subtitle,
                "printed_page_range": [page_start, page_end],
                "pdf_page_range": [page_start + 9, page_end + 9],
                "vocabulary": core.get(key, []),
                "primary_review_vocabulary": primary.get(key, []),
                "teaching": teaching.get(key, {}),
                "grammar_lab": GRAMMAR_LABS[ordinal],
                "textbook_tasks": tasks,
            }
        )
    return {
        "schema_version": "1.0",
        "source_id": "c7000000-0000-4000-8000-000000000001",
        "title": "人民教育出版社（PEP）英语七年级上册（新目标·2024版）",
        "source_files": {
            "core_vocabulary": CORE_PATH.name,
            "primary_vocabulary": PRIMARY_PATH.name,
            "teaching_analysis": TEACHING_PATH.name,
            "pdf": PDF_PATH.name,
        },
        "counts": {
            "units": len(units),
            "core_vocabulary": sum(len(unit["vocabulary"]) for unit in units),
            "primary_review_vocabulary": sum(len(unit["primary_review_vocabulary"]) for unit in units),
            "textbook_tasks": sum(len(unit["textbook_tasks"]) for unit in units),
        },
        "units": units,
    }


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    catalog = build_catalog()
    CATALOG_PATH.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(catalog["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
