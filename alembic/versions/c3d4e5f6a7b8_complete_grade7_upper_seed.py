"""complete grade 7 upper seed curriculum

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-19 01:30:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SOURCE_ID = "70000000-0000-4000-8000-000000000001"

NODES = [
    ("71000000-0000-4000-8000-000000000006", "Unit 3", "Is this your pencil?", 6, "13", "18"),
    ("71000000-0000-4000-8000-000000000007", "Unit 4", "Where's my schoolbag?", 7, "19", "24"),
    ("71000000-0000-4000-8000-000000000008", "Unit 5", "Do you have a soccer ball?", 8, "25", "30"),
    ("71000000-0000-4000-8000-000000000009", "Unit 6", "Do you like bananas?", 9, "31", "36"),
    ("71000000-0000-4000-8000-000000000010", "Unit 7", "How much are these socks?", 10, "37", "42"),
    ("71000000-0000-4000-8000-000000000011", "Unit 8", "When is your birthday?", 11, "43", "48"),
    ("71000000-0000-4000-8000-000000000012", "Unit 9", "My favorite subject is science.", 12, "49", "54"),
]

POINTS = [
    ("72000000-0000-4000-8000-000000000005", "71000000-0000-4000-8000-000000000002", "pattern.whats-this-english", "sentence_pattern", "What's this in English?", "询问某个物品用英语怎么表达。", "P.S5–S8"),
    ("72000000-0000-4000-8000-000000000006", "71000000-0000-4000-8000-000000000003", "pattern.what-color", "sentence_pattern", "What color is it?", "询问并描述物品的颜色。", "P.S9–S12"),
    ("72000000-0000-4000-8000-000000000007", "71000000-0000-4000-8000-000000000004", "grammar.be-verbs", "grammar", "am / is / are", "使用 be 动词介绍自己和他人。", "P.1–6"),
    ("72000000-0000-4000-8000-000000000008", "71000000-0000-4000-8000-000000000005", "grammar.demonstratives-family", "grammar", "this / that / these / those", "使用指示代词介绍家人。", "P.7–12"),
    ("72000000-0000-4000-8000-000000000009", "71000000-0000-4000-8000-000000000006", "grammar.possessive-pronouns", "grammar", "Possessive pronouns", "使用物主代词询问物品归属。", "P.13–18"),
    ("72000000-0000-4000-8000-000000000010", "71000000-0000-4000-8000-000000000007", "grammar.where-questions", "grammar", "Where questions", "使用 where 询问物品的位置。", "P.19–24"),
    ("72000000-0000-4000-8000-000000000011", "71000000-0000-4000-8000-000000000008", "grammar.have-has", "grammar", "have / has", "使用 have 和 has 谈论拥有的物品。", "P.25–30"),
    ("72000000-0000-4000-8000-000000000012", "71000000-0000-4000-8000-000000000009", "grammar.like-present", "grammar", "like in the simple present", "使用一般现在时表达食物喜好。", "P.31–36"),
    ("72000000-0000-4000-8000-000000000013", "71000000-0000-4000-8000-000000000010", "pattern.how-much", "sentence_pattern", "How much ...?", "询问商品价格并进行购物交流。", "P.37–42"),
    ("72000000-0000-4000-8000-000000000014", "71000000-0000-4000-8000-000000000011", "grammar.when-questions", "grammar", "When questions", "使用 when 询问日期和生日。", "P.43–48"),
    ("72000000-0000-4000-8000-000000000015", "71000000-0000-4000-8000-000000000012", "pattern.favorite-subject", "sentence_pattern", "What's your favorite subject?", "询问并说明最喜欢的学科及原因。", "P.49–54"),
]


def upgrade() -> None:
    for node_id, title, subtitle, ordinal, start_page, end_page in NODES:
        op.execute(sa.text("""
            INSERT INTO curriculum_nodes
              (id, source_id, node_type, title, subtitle, ordinal, start_page, end_page,
               estimated_minutes, learning_objectives)
            VALUES
              (CAST(:id AS uuid), CAST(:source_id AS uuid), 'unit', :title, :subtitle,
               :ordinal, :start_page, :end_page, 30, '[]'::jsonb)
            ON CONFLICT (id) DO NOTHING
        """).bindparams(id=node_id, source_id=SOURCE_ID, title=title, subtitle=subtitle, ordinal=ordinal, start_page=start_page, end_page=end_page))

    for point_id, node_id, key, point_type, title, summary, source_page in POINTS:
        op.execute(sa.text("""
            INSERT INTO knowledge_points
              (id, source_id, curriculum_node_id, canonical_key, type, title, summary,
               source_page, difficulty, status, content)
            VALUES
              (CAST(:id AS uuid), CAST(:source_id AS uuid), CAST(:node_id AS uuid),
               :key, :type, :title, :summary, :source_page, 0.3, 'published',
               '{"origin": "verified_seed"}'::jsonb)
            ON CONFLICT (canonical_key) DO NOTHING
        """).bindparams(id=point_id, source_id=SOURCE_ID, node_id=node_id, key=key, type=point_type, title=title, summary=summary, source_page=source_page))

    op.execute(sa.text("""
        UPDATE knowledge_sources
        SET unit_count = (SELECT count(*) FROM curriculum_nodes WHERE source_id = CAST(:source_id AS uuid)),
            knowledge_count = (SELECT count(*) FROM knowledge_points WHERE source_id = CAST(:source_id AS uuid))
        WHERE id = CAST(:source_id AS uuid)
    """).bindparams(source_id=SOURCE_ID))


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM knowledge_points WHERE id = ANY(CAST(:ids AS uuid[]))").bindparams(ids=[point[0] for point in POINTS]))
    op.execute(sa.text("DELETE FROM curriculum_nodes WHERE id = ANY(CAST(:ids AS uuid[]))").bindparams(ids=[node[0] for node in NODES]))
    op.execute(sa.text("""
        UPDATE knowledge_sources
        SET unit_count = (SELECT count(*) FROM curriculum_nodes WHERE source_id = CAST(:source_id AS uuid)),
            knowledge_count = (SELECT count(*) FROM knowledge_points WHERE source_id = CAST(:source_id AS uuid))
        WHERE id = CAST(:source_id AS uuid)
    """).bindparams(source_id=SOURCE_ID))
