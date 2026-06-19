"""add grade 7 upper textbook appendices

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-06-19 16:30:00.000000
"""

import json
import uuid
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SOURCE_ID = "70000000-0000-4000-8000-000000000001"
NODE_IDS = {
    "Starter Unit 1": "71000000-0000-4000-8000-000000000001",
    "Starter Unit 2": "71000000-0000-4000-8000-000000000002",
    "Starter Unit 3": "71000000-0000-4000-8000-000000000003",
    "Unit 1": "71000000-0000-4000-8000-000000000004",
    "Unit 2": "71000000-0000-4000-8000-000000000005",
    "Unit 3": "71000000-0000-4000-8000-000000000006",
    "Unit 4": "71000000-0000-4000-8000-000000000007",
    "Unit 5": "71000000-0000-4000-8000-000000000008",
    "Unit 6": "71000000-0000-4000-8000-000000000009",
    "Unit 7": "71000000-0000-4000-8000-000000000010",
    "Unit 8": "71000000-0000-4000-8000-000000000011",
    "Unit 9": "71000000-0000-4000-8000-000000000012",
}

NOTES = (
    (
        "Starter Unit 1",
        "55",
        ["英语名字的性别特征", "Good morning/afternoon/evening 与 Good night 的区别"],
    ),
    ("Starter Unit 2", "55–56", ["a 与 an 的选择", "in English 表示使用某种语言"]),
    ("Starter Unit 3", "55–56", ["五个元音字母", "in 表示在词语之中"]),
    (
        "Unit 1",
        "56–57",
        ["is/am 的缩略形式", "自我介绍句式", "英语姓名顺序与称谓", "ID card 与电话号码表达"],
    ),
    (
        "Unit 2",
        "56–57",
        ["中外亲属称谓差异", "Have a good day 与 You, too", "Here is/are", "宠物的人称代词"],
    ),
    (
        "Unit 3",
        "57–58",
        [
            "Excuse me",
            "What about",
            "Thanks for",
            "询问拼写",
            "Lost and Found",
            "ask somebody for something",
            "call/e-mail somebody at",
        ],
    ),
    ("Unit 4", "59", ["Come on", "and 与 but 构成并列句"]),
    ("Unit 5", "59–60", ["球类词汇辨析", "have/has", "I think", "sound + 形容词", "play 与 watch"]),
    (
        "Unit 6",
        "60–61",
        ["hamburger 与 salad 的文化知识", "think about", "what + 名词", "well 与 good"],
    ),
    ("Unit 7", "61–62", ["常见购物用语", "look 的用法", "pair", "价格 + for + 物品"]),
    ("Unit 8", "62–64", ["时间介词 in/on/at", "How old", "日期表达", "学校活动", "情态动词 can"]),
    (
        "Unit 9",
        "64–66",
        [
            "How’s your day",
            "why 与 because",
            "教师称谓",
            "for + 一段时间",
            "from ... to ...",
            "英文书信和电子邮件",
            "Is that OK with you",
        ],
    ),
)

PRONUNCIATION = (
    (
        "Starter Unit 1",
        "foundations",
        "75–78",
        "英语语音基础",
        ["44 个音素", "字母与字母组合的读音", "非重读音节", "英音和美音", "单词重音", "连读"],
    ),
    (
        "Starter Unit 1",
        "starter-1",
        "79",
        "Starter Unit 1 Pronunciation",
        ["/eɪ/ 与 /æ/", "/iː/ 与 /e/"],
    ),
    (
        "Starter Unit 2",
        "starter-2",
        "79",
        "Starter Unit 2 Pronunciation",
        ["/aɪ/ 与 /ɪ/", "/əʊ/ 与 /ɒ/（或 /ɑː, ɔː/）"],
    ),
    (
        "Starter Unit 3",
        "starter-3",
        "80",
        "Starter Unit 3 Pronunciation",
        ["字母 u 的 /juː/、/uː/、/ʌ/"],
    ),
    ("Unit 1", "unit-1", "80", "Unit 1 Pronunciation", ["/iː/ 与 /ɪ/", "/e/ 与 /æ/"]),
    ("Unit 2", "unit-2", "80", "Unit 2 Pronunciation", ["/uː/ 与 /ʊ/", "家庭介绍句群朗读"]),
    (
        "Unit 3",
        "unit-3",
        "81",
        "Unit 3 Pronunciation",
        ["/əʊ/ 与 /aʊ/", "/eɪ/ 与 /aɪ/", "/ɪə/ 与 /eə/"],
    ),
    ("Unit 4", "unit-4", "81", "Unit 4 Pronunciation", ["清浊辅音辨析", "位置问答朗读"]),
    ("Unit 5", "unit-5", "82", "Unit 5 Pronunciation", ["辅音音素与字母组合", "have/has 问答朗读"]),
    ("Unit 6", "unit-6", "82", "Unit 6 Pronunciation", ["多音节词重音", "名词复数 -s/-es 的读音"]),
    ("Unit 7", "unit-7", "83", "Unit 7 Pronunciation", ["e、ea、ear、ee 的读音", "购物句群朗读"]),
    ("Unit 8", "unit-8", "83", "Unit 8 Pronunciation", ["i、y 的读音", "日期与生日句群朗读"]),
    (
        "Unit 9",
        "unit-9",
        "84",
        "Unit 9 Pronunciation",
        ["o、ow、oo、ou 的读音", "学科话题句群朗读"],
    ),
)

GRAMMAR = (
    (
        "parts-of-speech",
        "Starter Unit 1",
        "85",
        "词类（Parts of Speech）",
        "识别本册十类词。",
        list(NODE_IDS),
    ),
    (
        "nouns-countability",
        "Unit 6",
        "85–86",
        "可数名词与不可数名词",
        "区分可数与不可数名词。",
        ["Unit 2", "Unit 3", "Unit 6", "Unit 7"],
    ),
    (
        "noun-plurals",
        "Unit 2",
        "85–86",
        "名词复数的构成与读音",
        "掌握规则、不规则复数及读音。",
        ["Unit 2", "Unit 3", "Unit 6", "Unit 7"],
    ),
    (
        "noun-possessive",
        "Unit 8",
        "86",
        "名词所有格",
        "使用 ’s、’ 表达所属关系。",
        ["Unit 2", "Unit 8"],
    ),
    (
        "articles",
        "Starter Unit 2",
        "87",
        "冠词（Articles）",
        "使用 the、a/an 和零冠词。",
        ["Starter Unit 2", "Unit 3", "Unit 5", "Unit 6"],
    ),
    (
        "personal-pronouns",
        "Unit 1",
        "87",
        "人称代词",
        "区分人称代词主格和宾格。",
        ["Unit 1", "Unit 2", "Unit 5", "Unit 9"],
    ),
    (
        "possessive-pronouns",
        "Unit 3",
        "87–88",
        "物主代词",
        "区分形容词性和名词性物主代词。",
        ["Unit 1", "Unit 3", "Unit 4"],
    ),
    (
        "demonstratives",
        "Unit 2",
        "88",
        "指示代词",
        "使用 this、that、these、those。",
        ["Unit 2", "Unit 3", "Unit 7"],
    ),
    (
        "cardinal-numbers",
        "Unit 1",
        "88",
        "基数词",
        "表达号码、数量、年龄和价格。",
        ["Unit 1", "Unit 5", "Unit 7", "Unit 8"],
    ),
    ("ordinal-numbers", "Unit 8", "89", "序数词", "使用序数词表达日期和顺序。", ["Unit 8"]),
    (
        "simple-present-be",
        "Unit 1",
        "89–90",
        "一般现在时：be 动词",
        "掌握 am/is/are 的陈述、否定和疑问结构。",
        ["Unit 1", "Unit 2", "Unit 4", "Unit 8", "Unit 9"],
    ),
    (
        "simple-present-verbs",
        "Unit 5",
        "90–91",
        "一般现在时：实义动词",
        "掌握第三人称单数及 do/does。",
        ["Unit 5", "Unit 6", "Unit 9"],
    ),
    (
        "prepositions",
        "Unit 4",
        "91–92",
        "介词（Prepositions）",
        "掌握本册常用介词短语。",
        ["Starter Unit 2", "Unit 2", "Unit 3", "Unit 4", "Unit 7", "Unit 8", "Unit 9"],
    ),
    (
        "sentence-types",
        "Starter Unit 1",
        "92",
        "句子种类",
        "区分陈述句、疑问句、祈使句和感叹句。",
        list(NODE_IDS),
    ),
    (
        "yes-no-questions",
        "Unit 3",
        "93",
        "一般疑问句",
        "使用 be、do/does 提问并简略回答。",
        ["Unit 1", "Unit 3", "Unit 5", "Unit 6"],
    ),
    (
        "wh-questions",
        "Unit 9",
        "93",
        "特殊疑问句",
        "使用 what、who、where、when、why、how。",
        [
            "Starter Unit 2",
            "Starter Unit 3",
            "Unit 1",
            "Unit 2",
            "Unit 4",
            "Unit 7",
            "Unit 8",
            "Unit 9",
        ],
    ),
)


def _insert(
    key: str, node: str, point_type: str, title: str, summary: str, page: str, content: dict
) -> None:
    point_id = str(uuid.uuid5(uuid.UUID(SOURCE_ID), key))
    op.execute(
        sa.text("""
        INSERT INTO knowledge_points
          (id, source_id, curriculum_node_id, canonical_key, type, title, summary,
           source_page, difficulty, status, content)
        VALUES
          (CAST(:id AS uuid), CAST(:source_id AS uuid), CAST(:node_id AS uuid), :key,
           :type, :title, :summary, :page, :difficulty, 'published', CAST(:content AS jsonb))
        ON CONFLICT (canonical_key) DO NOTHING
    """).bindparams(
            id=point_id,
            source_id=SOURCE_ID,
            node_id=NODE_IDS[node],
            key=key,
            type=point_type,
            title=title,
            summary=summary,
            page=f"P.{page}",
            difficulty=0.35 if point_type != "text_note" else 0.3,
            content=json.dumps(content, ensure_ascii=False),
        )
    )


def upgrade() -> None:
    for unit, page, topics in NOTES:
        slug = unit.lower().replace(" ", "-")
        _insert(
            f"notes-on-text.{slug}.seed",
            unit,
            "text_note",
            f"{unit} Notes on the Text",
            "教材重点句式、语法用法与地道英语文化注释。",
            page,
            {"origin": "verified_appendix_seed", "role": "unit_reference", "topics": topics},
        )
    for unit, slug, page, title, focus in PRONUNCIATION:
        _insert(
            f"pronunciation.{slug}.seed",
            unit,
            "pronunciation",
            title,
            "本册核心音素、拼读规则与朗读训练。",
            page,
            {
                "origin": "verified_appendix_seed",
                "role": "core_pronunciation",
                "priority": "core",
                "focus": focus,
            },
        )
    for slug, unit, page, title, summary, related in GRAMMAR:
        _insert(
            f"grammar-reference.{slug}.seed",
            unit,
            "grammar",
            title,
            summary,
            page,
            {
                "origin": "verified_appendix_seed",
                "role": "grammar_reference",
                "primary_unit": unit,
                "related_units": related,
                "mapping_basis": "教材单元目标语言、Grammar Focus 与附录例句",
            },
        )
    op.execute(
        sa.text("""
        UPDATE knowledge_sources
        SET knowledge_count = (
                SELECT count(*) FROM knowledge_points
                WHERE source_id = CAST(:source_id AS uuid)
            ),
            metadata = COALESCE(metadata, '{}'::jsonb) ||
                '{"appendices": {"notes": 12, "pronunciation": 13,
                  "grammar": 16}, "unit_wordlist_entries": 431}'::jsonb
        WHERE id = CAST(:source_id AS uuid)
    """).bindparams(source_id=SOURCE_ID)
    )


def downgrade() -> None:
    op.execute(
        sa.text("""
        DELETE FROM knowledge_points
        WHERE source_id = CAST(:source_id AS uuid)
          AND (canonical_key LIKE 'notes-on-text.%.seed'
            OR canonical_key LIKE 'pronunciation.%.seed'
            OR canonical_key LIKE 'grammar-reference.%.seed')
    """).bindparams(source_id=SOURCE_ID)
    )
    op.execute(
        sa.text("""
        UPDATE knowledge_sources
        SET knowledge_count = (
                SELECT count(*) FROM knowledge_points
                WHERE source_id = CAST(:source_id AS uuid)
            ),
            metadata = COALESCE(metadata, '{}'::jsonb) - 'appendices' - 'unit_wordlist_entries'
        WHERE id = CAST(:source_id AS uuid)
    """).bindparams(source_id=SOURCE_ID)
    )
