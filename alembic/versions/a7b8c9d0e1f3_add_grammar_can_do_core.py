"""add grammar can-do core

Revision ID: a7b8c9d0e1f3
Revises: z6a7b8c9d0e1
"""

from typing import Sequence, Union
import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a7b8c9d0e1f3"
down_revision: Union[str, Sequence[str], None] = "z6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CATALOG = [
    ("be-affirmative", "be 动词", "肯定句", "A1", "FORM", "能根据主语选择 am、is 或 are 构成肯定句。", "I am a student."),
    ("be-negative", "be 动词", "否定句", "A1", "FORM", "能在 am、is、are 后加 not 构成否定句。", "She isn't at home."),
    ("be-questions", "be 动词", "疑问句", "A1", "FORM", "能把 be 动词提前构成一般疑问句并作简短回答。", "Are you in Class One?"),
    ("subject-pronouns", "代词", "人称代词", "A1", "FORM", "能用正确的主格人称代词作句子主语。", "They are my friends."),
    ("this-that", "限定词与代词", "指示词", "A1", "FORM+USE", "能根据距离和单复数选择 this、that、these、those。", "These are my books."),
    ("a-an", "名词与限定词", "不定冠词", "A1", "FORM", "能根据后接词的语音选择 a 或 an。", "It is an orange."),
    ("plural-nouns", "名词与限定词", "名词复数", "A1", "FORM", "能构成常见规则和高频不规则名词复数。", "Two children are playing."),
    ("possessive-s", "名词与限定词", "所有格", "A1", "FORM+USE", "能用名词所有格 's 表达所属关系。", "This is Tom's bag."),
    ("possessive-determiners", "限定词与代词", "物主限定词", "A1", "FORM+USE", "能根据所有者选择 my、your、his、her、our、their。", "Her name is Alice."),
    ("there-is-are", "句子结构", "存在句", "A1", "FORM+USE", "能根据后接名词单复数选择 there is 或 there are。", "There are two maps on the wall."),
    ("there-questions", "句子结构", "存在句疑问", "A1", "FORM", "能构成 Is there / Are there 疑问句并作简短回答。", "Is there a library nearby?"),
    ("some-any", "名词与限定词", "数量限定", "A1", "FORM+USE", "能在常见肯定、否定和疑问语境中选择 some 或 any。", "Do you have any milk?"),
    ("place-prepositions", "介词", "地点介词", "A1", "USE", "能用 in、on、under、behind、next to 描述位置。", "The keys are under the chair."),
    ("present-simple-affirmative", "时态与体", "一般现在时", "A1", "FORM+USE", "能用一般现在时表达习惯和经常发生的动作。", "I walk to school every day."),
    ("third-person-s", "时态与体", "第三人称单数", "A1", "FORM", "能在一般现在时第三人称单数主语后使用正确动词形式。", "She watches TV after dinner."),
    ("do-does-questions", "时态与体", "一般现在时疑问", "A1", "FORM", "能用 do 或 does 构成一般现在时疑问句并恢复动词原形。", "Does he like music?"),
    ("present-simple-negative", "时态与体", "一般现在时否定", "A1", "FORM", "能用 don't 或 doesn't 构成一般现在时否定句。", "He doesn't play tennis."),
    ("frequency-adverbs", "副词", "频度副词", "A2", "USE", "能把 always、usually、often、sometimes、never 放在合适位置。", "She usually gets up at seven."),
    ("can-ability", "情态与语气", "can 表能力", "A1", "FORM+USE", "能用 can / can't 加动词原形表达能力。", "I can swim, but I can't skate."),
    ("can-questions", "情态与语气", "can 疑问句", "A1", "FORM", "能把 can 提前构成一般疑问句并作简短回答。", "Can you play the guitar?"),
    ("wh-questions", "疑问结构", "特殊疑问句", "A1", "FORM+USE", "能选择 what、who、where、when、why、how 获取所需信息。", "Where does your sister work?"),
    ("what-time-when", "疑问结构", "时间提问", "A1", "USE", "能区分 what time 对具体时刻和 when 对较宽时间的提问。", "What time do you go to bed?"),
    ("how-many-much", "疑问结构", "数量提问", "A2", "FORM+USE", "能根据可数与不可数名词选择 how many 或 how much。", "How many books do you have?"),
    ("and-but-because", "连接与从句", "基础连接词", "A2", "USE", "能用 and 表并列、but 表转折、because 引出原因。", "I like it because it is useful."),
    ("imperatives", "句子结构", "祈使句", "A1", "FORM+USE", "能用动词原形和 Don't 构成肯定、否定祈使句。", "Please close the door."),
    ("ordinal-dates", "名词与限定词", "序数词与日期", "A2", "FORM+USE", "能用序数词正确表达英语日期。", "My birthday is on May fifth."),
    ("present-continuous", "时态与体", "现在进行时", "A1", "FORM+USE", "能用 be + doing 描述说话时正在发生的动作。", "They are doing their homework."),
    ("like-doing", "非谓语", "动名词", "A2", "FORM+USE", "能用 like / love / enjoy + doing 表达兴趣偏好。", "She enjoys reading stories."),
    ("want-to-do", "非谓语", "不定式", "A2", "FORM+USE", "能用 want / need + to do 表达意愿或需要。", "I want to join the art club."),
    ("object-pronouns", "代词", "宾格代词", "A1", "FORM", "能在动词或介词后使用 me、you、him、her、us、them。", "Please help me."),
]


def upgrade() -> None:
    op.alter_column("knowledge_points", "source_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)
    op.alter_column("knowledge_points", "curriculum_node_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)
    op.create_table(
        "grammar_can_do_profiles",
        sa.Column("knowledge_point_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category", sa.String(60), nullable=False),
        sa.Column("subcategory", sa.String(100), nullable=False),
        sa.Column("cefr_level", sa.String(4), nullable=False),
        sa.Column("construct_type", sa.String(20), nullable=False),
        sa.Column("can_do_statement", sa.Text(), nullable=False),
        sa.Column("success_criteria", postgresql.JSONB(), nullable=False),
        sa.Column("failure_criteria", postgresql.JSONB(), nullable=False),
        sa.Column("positive_examples", postgresql.JSONB(), nullable=False),
        sa.Column("negative_examples", postgresql.JSONB(), nullable=False),
        sa.Column("prerequisites", postgresql.JSONB(), nullable=False),
        sa.Column("detection_hints", postgresql.JSONB(), nullable=False),
        sa.Column("catalog_version", sa.String(40), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["knowledge_point_id"], ["knowledge_points.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("knowledge_point_id", name="uq_grammar_can_do_profile_point"),
    )
    op.create_index("ix_grammar_can_do_profiles_knowledge_point_id", "grammar_can_do_profiles", ["knowledge_point_id"])
    op.create_index("ix_grammar_can_do_category_cefr", "grammar_can_do_profiles", ["category", "cefr_level"])
    op.create_table(
        "grammar_curriculum_mappings",
        sa.Column("knowledge_point_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("curriculum_node_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("relation_type", sa.String(20), nullable=False),
        sa.Column("evidence_source", sa.String(80), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["knowledge_point_id"], ["knowledge_points.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["curriculum_node_id"], ["curriculum_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("knowledge_point_id", "curriculum_node_id", name="uq_grammar_curriculum_mapping"),
    )
    op.create_index("ix_grammar_curriculum_mappings_knowledge_point_id", "grammar_curriculum_mappings", ["knowledge_point_id"])
    op.create_index("ix_grammar_curriculum_mappings_curriculum_node_id", "grammar_curriculum_mappings", ["curriculum_node_id"])

    kp = sa.table("knowledge_points", sa.column("id"), sa.column("source_id"), sa.column("curriculum_node_id"), sa.column("canonical_key"), sa.column("type"), sa.column("title"), sa.column("summary"), sa.column("source_page"), sa.column("difficulty"), sa.column("status"), sa.column("content", postgresql.JSONB()))
    profile = sa.table("grammar_can_do_profiles", sa.column("id"), sa.column("knowledge_point_id"), sa.column("category"), sa.column("subcategory"), sa.column("cefr_level"), sa.column("construct_type"), sa.column("can_do_statement"), sa.column("success_criteria", postgresql.JSONB()), sa.column("failure_criteria", postgresql.JSONB()), sa.column("positive_examples", postgresql.JSONB()), sa.column("negative_examples", postgresql.JSONB()), sa.column("prerequisites", postgresql.JSONB()), sa.column("detection_hints", postgresql.JSONB()), sa.column("catalog_version"))
    conn = op.get_bind()
    namespace = uuid.UUID("53bdfc82-92d5-4d87-9d59-57cbfd31197a")
    for slug, category, subcategory, cefr, construct_type, statement, example in CATALOG:
        point_id = uuid.uuid5(namespace, slug)
        conn.execute(kp.insert().values(id=point_id, source_id=None, curriculum_node_id=None, canonical_key=f"grammar.g7.v1.{slug}", type="grammar_can_do", title=statement.removesuffix("。"), summary=statement, source_page="catalog:g7-v1", difficulty={"A1": 0.25, "A2": 0.4}.get(cefr, 0.5), status="published", content={"pilot": "grade7", "slug": slug}))
        conn.execute(profile.insert().values(id=uuid.uuid5(namespace, f"profile:{slug}"), knowledge_point_id=point_id, category=category, subcategory=subcategory, cefr_level=cefr, construct_type=construct_type, can_do_statement=statement, success_criteria=["目标形式正确", "语义符合任务语境"], failure_criteria=["目标形式错误或缺失", "形式正确但语义不匹配"], positive_examples=[example], negative_examples=[], prerequisites=[], detection_hints={"assessment_modes": ["recognition", "recall", "production"]}, catalog_version="g7-v1"))


def downgrade() -> None:
    op.execute("DELETE FROM knowledge_points WHERE canonical_key LIKE 'grammar.g7.v1.%'")
    op.drop_table("grammar_curriculum_mappings")
    op.drop_table("grammar_can_do_profiles")
    op.alter_column("knowledge_points", "curriculum_node_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)
    op.alter_column("knowledge_points", "source_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)
