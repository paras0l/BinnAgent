"""add current Changsha grade 7 English public textbooks

Revision ID: t0u1v2w3x4y5
Revises: s9t0u1v2w3x4
Create Date: 2026-07-11 12:00:00.000000
"""

import json
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "t0u1v2w3x4y5"
down_revision: Union[str, Sequence[str], None] = "s9t0u1v2w3x4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UPPER_SOURCE_ID = "c7000000-0000-4000-8000-000000000001"
LOWER_SOURCE_ID = "c7000000-0000-4000-8000-000000000002"

SOURCES = (
    (
        UPPER_SOURCE_ID,
        "长沙市英语 七年级上册（新目标·2024版）",
        "upper",
        "changsha-pep-grade7-upper-2024",
        "1" * 64,
        (
            ("Starter Unit 1", "Hello!"),
            ("Starter Unit 2", "Keep Tidy!"),
            ("Starter Unit 3", "Welcome!"),
            ("Unit 1", "You and Me"),
            ("Unit 2", "We're Family!"),
            ("Unit 3", "My School"),
            ("Unit 4", "My Favourite Subject"),
            ("Unit 5", "Fun Clubs"),
            ("Unit 6", "A Day in the Life"),
            ("Unit 7", "Happy Birthday!"),
        ),
    ),
    (
        LOWER_SOURCE_ID,
        "长沙市英语 七年级下册（新目标·2024版）",
        "lower",
        "changsha-pep-grade7-lower-2024",
        "2" * 64,
        (
            ("Unit 1", "Animal Friends"),
            ("Unit 2", "No Rules, No Order"),
            ("Unit 3", "Keep Fit"),
            ("Unit 4", "Eat Well"),
            ("Unit 5", "Here and Now"),
            ("Unit 6", "Rain or Shine"),
            ("Unit 7", "A Day to Remember"),
            ("Unit 8", "Once upon a Time"),
        ),
    ),
)

MATERIALS = {
    "Hello!": ("学习日常问候、介绍姓名并认识常见课堂用语。", "be 动词 am/is/are；问候与自我介绍。", ["hello", "name", "class", "teacher", "student"]),
    "Keep Tidy!": ("描述个人物品的位置、颜色和归属，养成整理习惯。", "指示代词 this/that/these/those；物主代词。", ["tidy", "book", "schoolbag", "desk", "whose"]),
    "Welcome!": ("认识校园中的人物、地点和常见活动。", "There be 句型；where 引导的特殊疑问句。", ["welcome", "school", "library", "building", "playground"]),
    "You and Me": ("交换姓名、年龄、国籍与兴趣等个人信息。", "一般现在时 be 动词；what/where/how old 问句。", ["country", "age", "grade", "hobby", "information"]),
    "We're Family!": ("介绍家庭成员、职业、外貌与家庭活动。", "have/has；名词所有格；who 引导的问句。", ["family", "parent", "cousin", "grandparent", "together"]),
    "My School": ("介绍学校设施、方位和喜欢的校园空间。", "There be 句型；方位介词；地点描述。", ["hall", "office", "laboratory", "behind", "between"]),
    "My Favourite Subject": ("谈论课程、任课教师、上课时间及喜欢的原因。", "why/because；星期与时间表达；形容词作表语。", ["subject", "science", "history", "useful", "interesting"]),
    "Fun Clubs": ("了解校园社团，表达能力、兴趣和加入意愿。", "情态动词 can；want to；动词-ing 作兴趣表达。", ["club", "join", "skill", "drama", "volunteer"]),
    "A Day in the Life": ("描述自己或他人的日常作息与学习安排。", "一般现在时；频度副词；时间表达。", ["routine", "usually", "exercise", "breakfast", "homework"]),
    "Happy Birthday!": ("询问生日和日期，策划生日活动并表达祝愿。", "日期与序数词；when 引导的问句；名词所有格。", ["birthday", "date", "month", "celebrate", "present"]),
    "Animal Friends": ("描述动物的外貌、习性与能力，理解人与动物的关系。", "一般现在时；can；形容词描述特征。", ["animal", "panda", "giraffe", "wild", "protect"]),
    "No Rules, No Order": ("理解家规、校规和公共规则，并说明规则的意义。", "祈使句；must/have to；规则表达。", ["rule", "order", "must", "follow", "allowed"]),
    "Keep Fit": ("交流运动习惯、身体状态与健康生活方式。", "一般现在时；how often；频度表达。", ["fit", "health", "exercise", "habit", "energy"]),
    "Eat Well": ("谈论食物、饮食选择和均衡饮食。", "可数与不可数名词；some/any；数量表达。", ["meal", "vegetable", "protein", "healthy", "balance"]),
    "Here and Now": ("描述此刻正在发生的活动、人物动作和现场情景。", "现在进行时；现在分词；一般疑问句。", ["moment", "happen", "wait", "carry", "photo"]),
    "Rain or Shine": ("谈论天气、季节、出行安排和天气变化。", "天气表达；一般将来安排；条件与建议。", ["weather", "forecast", "sunny", "storm", "temperature"]),
    "A Day to Remember": ("叙述一次难忘经历，按时间顺序组织事件。", "一般过去时；规则与不规则动词；时间连接词。", ["remember", "event", "suddenly", "finally", "experience"]),
    "Once upon a Time": ("阅读和复述故事，理解人物、情节与寓意。", "一般过去时；故事连接词；直接引语基础。", ["story", "character", "journey", "decide", "ending"]),
}

QUESTIONS = {
    "Hello!": ("Complete the greeting: ___, Helen!", "Hello", ["Hello", "Goodbye", "Thanks", "Sorry"], "Hello is a greeting."),
    "Keep Tidy!": ("Complete the classroom reminder: Keep your desk ___.", "tidy", ["tidy", "late", "tall", "loud"], "Tidy means clean and well organised."),
    "Welcome!": ("Complete the greeting: ___ to our school!", "Welcome", ["Welcome", "Close", "Leave", "Count"], "We use welcome when greeting a visitor."),
    "You and Me": ("Complete: My favourite ___ is playing tennis.", "hobby", ["hobby", "country", "grade", "age"], "A hobby is an activity you enjoy in your free time."),
    "We're Family!": ("Complete: We are a happy ___.", "family", ["family", "class", "club", "subject"], "Family names the group of related people."),
    "My School": ("Complete: The science lab is ___ the library and the hall.", "between", ["between", "usually", "together", "useful"], "Between describes a position in the middle of two places."),
    "My Favourite Subject": ("Complete: I like science ___ it is interesting.", "because", ["because", "but", "before", "where"], "Because introduces the reason."),
    "Fun Clubs": ("Complete: I can sing, so I want to ___ the music club.", "join", ["join", "carry", "count", "celebrate"], "Join means become a member of a group."),
    "A Day in the Life": ("Complete: I ___ do my homework after dinner.", "usually", ["usually", "birthday", "between", "country"], "Usually is a frequency adverb for a regular routine."),
    "Happy Birthday!": ("Complete: My birthday is in May. What is the ___?", "date", ["date", "subject", "routine", "skill"], "A date identifies a day in a month and year."),
    "Animal Friends": ("Complete: We should ___ wild animals.", "protect", ["protect", "invite", "order", "carry"], "Protect means keep someone or something safe."),
    "No Rules, No Order": ("Complete: We ___ follow the school rules.", "must", ["must", "can", "would", "are"], "Must expresses a strong obligation."),
    "Keep Fit": ("Complete: Regular exercise keeps us ___.", "fit", ["fit", "wild", "sunny", "late"], "Fit means healthy and strong."),
    "Eat Well": ("Complete: A ___ diet includes different kinds of food.", "balanced", ["balanced", "stormy", "tidy", "funny"], "A balanced diet provides the nutrients the body needs."),
    "Here and Now": ("Complete: Look! The students ___ a photo.", "are taking", ["are taking", "take", "took", "takes"], "Look signals an action happening now, so use the present continuous."),
    "Rain or Shine": ("Complete: Take an umbrella. The forecast says it will be ___.", "rainy", ["rainy", "tidy", "wild", "useful"], "Rainy describes weather with rain."),
    "A Day to Remember": ("Complete: Yesterday we ___ a wonderful school event.", "had", ["had", "have", "has", "having"], "Yesterday calls for the past form had."),
    "Once upon a Time": ("Complete: Once upon a time, a girl ___ on a journey.", "went", ["went", "goes", "going", "go"], "Went is the past form of go in a story."),
}

NAMESPACE = uuid.UUID("8fe269df-9361-4d0c-b2c9-63ea36f197aa")


def upgrade() -> None:
    connection = op.get_bind()
    for source_id, title, volume, manifest_id, sha256, units in SOURCES:
        metadata = {
            "source_kind": "public_textbook",
            "public_textbook_seed": True,
            "availability_status": "available",
            "quality_status": "published",
            "parser_status": "catalog_curated",
            "book_manifest_id": manifest_id,
            "subject": "english",
            "province": "湖南省",
            "city": "长沙市",
            "curriculum_standard": "义务教育英语课程标准（2022年版）",
            "edition_year": 2024,
            "effective_school_year": "2024-2025",
            "selection_basis": "长沙市城区2025年春季义务教育七年级课程用书价格表",
            "selection_basis_url": "https://jyt.hunan.gov.cn/jyt/sjyt/xxgk/c100951/202503/t20250310_33607705.html",
            "official_material_url": (
                "https://basic.smartedu.cn/tchMaterial"
            ),
            "official_material_note": "在国家中小学智慧教育平台按人教版、七年级、英语和册次查看教材正文",
            "copyright_policy": "catalog metadata and short structured facts only; no textbook full text",
        }
        connection.execute(
            sa.text(
                """
                INSERT INTO knowledge_sources
                  (id, owner_learner_id, title, filename, publisher, edition, grade, volume,
                   status, visibility, object_key, sha256, file_size, page_count, unit_count,
                   knowledge_count, metadata)
                VALUES
                  (CAST(:id AS uuid), NULL, :title, :filename, '人民教育出版社（PEP）',
                   '人教新目标（2024版）', 'grade-7', :volume, 'published', 'public', NULL,
                   :sha256, 0, NULL, :unit_count, :knowledge_count, CAST(:metadata AS jsonb))
                ON CONFLICT (id) DO NOTHING
                """
            ).bindparams(
                id=source_id,
                title=title,
                filename=f"义务教育教科书·英语七年级{'上' if volume == 'upper' else '下'}册（2024版）",
                volume=volume,
                sha256=sha256,
                unit_count=len(units),
                knowledge_count=len(units) * 3,
                metadata=json.dumps(metadata, ensure_ascii=False),
            )
        )
        for ordinal, (unit_title, subtitle) in enumerate(units, 1):
            node_id = f"c7{1 if volume == 'upper' else 2}{ordinal:02d}000-0000-4000-8000-000000000001"
            connection.execute(
                sa.text(
                    """
                    INSERT INTO curriculum_nodes
                      (id, source_id, parent_id, node_type, title, subtitle, ordinal,
                       estimated_minutes, learning_objectives)
                    VALUES
                      (CAST(:id AS uuid), CAST(:source_id AS uuid), NULL, 'unit', :title,
                       :subtitle, :ordinal, 30, '[]'::jsonb)
                    ON CONFLICT (id) DO NOTHING
                    """
                ).bindparams(
                    id=node_id,
                    source_id=source_id,
                    title=unit_title,
                    subtitle=subtitle,
                    ordinal=ordinal,
                )
            )
            overview, grammar, vocabulary = MATERIALS[subtitle]
            point_specs = (
                ("text_note", f"{subtitle} 单元导学", overview, {"role": "unit_overview"}),
                ("grammar", f"{subtitle} 核心语法", grammar, {"role": "grammar_summary"}),
                (
                    "vocabulary",
                    f"{subtitle} 核心词汇",
                    "、".join(vocabulary),
                    {"role": "vocabulary_preview", "words": vocabulary},
                ),
            )
            for point_order, (point_type, point_title, summary, content) in enumerate(
                point_specs, 1
            ):
                stable_key = f"{manifest_id}:unit:{ordinal:02d}:{point_type}:{point_order}"
                point_id = uuid.uuid5(NAMESPACE, stable_key)
                point_content = {
                    **content,
                    "origin": "curated_learning_material",
                    "stable_key": stable_key,
                    "confidence": 0.9,
                    "requires_review": False,
                    "copyright_note": "Original summary; not textbook full text",
                    "selection_basis_url": metadata["selection_basis_url"],
                }
                connection.execute(
                    sa.text(
                        """
                        INSERT INTO knowledge_points
                          (id, source_id, curriculum_node_id, canonical_key, type, title,
                           summary, source_page, difficulty, status, content)
                        VALUES
                          (:id, CAST(:source_id AS uuid), CAST(:node_id AS uuid), :canonical_key,
                           :type, :title, :summary, :source_page, :difficulty, 'published',
                           CAST(:content AS jsonb))
                        ON CONFLICT (id) DO NOTHING
                        """
                    ).bindparams(
                        id=point_id,
                        source_id=source_id,
                        node_id=node_id,
                        canonical_key=stable_key,
                        type=point_type,
                        title=point_title,
                        summary=summary,
                        source_page=f"Unit {ordinal}",
                        difficulty=0.18 if volume == "upper" else 0.28,
                        content=json.dumps(point_content, ensure_ascii=False),
                    )
                )
            stem, answer, options, explanation = QUESTIONS[subtitle]
            question_key = f"{manifest_id}:unit:{ordinal:02d}:daily-classroom-check"
            question_id = uuid.uuid5(NAMESPACE, question_key)
            vocabulary_point_id = uuid.uuid5(
                NAMESPACE, f"{manifest_id}:unit:{ordinal:02d}:vocabulary:3"
            )
            connection.execute(
                sa.text(
                    """
                    INSERT INTO exercise_questions
                      (id, source_id, curriculum_node_id, knowledge_point_id, question_type,
                       stem, options, answer, explanation, difficulty, status, metadata)
                    VALUES
                      (:id, CAST(:source_id AS uuid), CAST(:node_id AS uuid), :point_id,
                       'single_choice', :stem, CAST(:options AS jsonb), :answer, :explanation,
                       :difficulty, 'published', CAST(:metadata AS jsonb))
                    ON CONFLICT (id) DO NOTHING
                    """
                ).bindparams(
                    id=question_id,
                    source_id=source_id,
                    node_id=node_id,
                    point_id=vocabulary_point_id,
                    stem=stem,
                    options=json.dumps(options, ensure_ascii=False),
                    answer=answer,
                    explanation=explanation,
                    difficulty=0.2 if volume == "upper" else 0.3,
                    metadata=json.dumps(
                        {
                            "origin": "curated_daily_classroom_check",
                            "stable_key": question_key,
                            "source_stable_id": manifest_id,
                        },
                        ensure_ascii=False,
                    ),
                )
            )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM knowledge_sources "
            "WHERE id IN (CAST(:upper AS uuid), CAST(:lower AS uuid))"
        )
        .bindparams(upper=UPPER_SOURCE_ID, lower=LOWER_SOURCE_ID)
    )
