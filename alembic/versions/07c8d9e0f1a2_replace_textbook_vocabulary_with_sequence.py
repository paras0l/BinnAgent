"""replace textbook vocabulary with sequence-only records

Revision ID: 07c8d9e0f1a2
Revises: g7b8c9d0e1f2
Create Date: 2026-06-21 15:00:00.000000
"""

import base64
import json
import re
import uuid
import zlib
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "07c8d9e0f1a2"
down_revision: Union[str, Sequence[str], None] = "g7b8c9d0e1f2"
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

_SEQUENCE_DATA = (
    "c-nQF+mhq95r$ud_Dyc=i2+cfnTu3v54P8i$9C0j;!34*0a1|16-6jKj8?hwYvcv;V0n^&-2liRgRR=>zo~AXK7u"
    "%M|M8D6-;cT<O<(-AYsNx+`PG+4YxhyaKflVPoNeDV-Er;7Y~uIsAcfEQ!XLDV`>5<bb>mH$51Y2Ni*B+>`rtM@Y"
    "diGsKYx)iD_-VmzioCu^K3kY=skS?1U@GoKJN3FzfF4$R(zAc$KC`h@{j3er(i|?`Mk5&!X2S-Ie+HUg-y3h{_*_"
    "a{@lY6`KP1L-iZ8zIW(P#BJ$5;taW!9R*uN?|K%^v*prLrvA=sg-_p*-^N8QPb*6HKT;>74e*MPT-L7&OdBCsQrl"
    "N<yD)W$E+ueMe*~&cAH%+&{%@@Ne^K9Shc0SpjMCSQ^+c(u*AW3AN?{~e!IzI$fnWy`Guj$^7tnxFAO=~)S8)ua-"
    "NlO>K)_RO0vMJ5rjm(C}x*4LV{1G~D%53=C?$|a%J;Mp!<}=4BmRz?H)9<tCXMG8Fn@y;uORx{wgnnvGzi1xeg)o"
    "!N)CY5hb&vCCR*uM%{-~>y8CQ<TBR`p2up&?VUsKbLi;6t>X7onnd29X?_n&$2RCHKGp73ySZNZ`<kNMIXJ(!gv@"
    "}z%${mR*Hr?VBqobl^?kZh$u+>YL4sslBb1l!tvQISpR%|6)tQEqedcU?Iun|ACC6&$Z+Hfh&RCd%eBDXy?AdY?_"
    "Y*3D=Z-DZ<6Q-7g)EI1GO6ZZDnE&7;E8fz15=B1c3I$}gt<Vg?41S>xCz;qX^$WtElEm)C9e7<=j@_gUV`)6N*Ir"
    "=p3oGt!y^e6Y1FZOfvuiyRR>~yf%0zYTGdGq0K^9@$xb13q$e(&_zL=hO`wvR<ZXtdra`1x$8-eD<|J#4TW2)M3D"
    "ALSlGPs81Ow859ORR?ki_5lLA+XwrIdr<vLR^a{L%n+==+aIXxkrgsInl}P(zq8(mGWmTBR^ZM5+w?Yyz`M89ks>"
    "Sb{>Q5gRv>_}?u}VgAcX^?W=YDyp?Nk@WJ03(6s$xN!`#VTR3Z=49P4pWnNZ=LB8x;Wqw8&4Y9_GqB@*hU^Nt>Da"
    "3pdHM+kdA<j?U(vPC@F=K?aJ+4RG>sQTt*wD51&dP5=GR?|UPlzb5jhgkUvDIfaAP`M9|Le6jMrkk7Kid7-$bF<%"
    "5Z5<qijEAbWwp}@Do7umJY00)i=HK(B9QjI+=Z~iA=1TM<Yl%ExV{=g=#aAs=;hLmGiXZHmY941xB=^*u_|9i3k="
    "l>k9DXDzk=c{(skSF6lRB$uxwCinPKmsJawC8lLCab`Bxj`p`;nwXKHp<Yzd=6l&&@dZX9w2J!iPFg%`nnc1qZ`t"
    "J8}&f90}or_Tk_t2w&WYvKv=U31Rod{O-})K!O{9bo+P-uyy}3F<uO8ZC@tF%Yv<k<j&k<x~-f?2#>WL%%ZENg9k"
    "k}Sb;ok?TwJh@r*wnsZeS37DXV$D|did1oEpjRoyHCk?pDDLRKK7cP_oq1x;1B_!s^NtDm5Cp(lAW!3qR5&_oPbi"
    "I6Hg4K#2Ijug2^wf3Y;3g<akiNN$k&zD7(nL?%4p4=p8_Q6VoHgy$MiC*P4*>7^q85P0Bl}O5!NfSjPE7zz{_sOe"
    "5UiRRPLQb9eG)7TK=+ac<L??`%LQ==3Z=)zAwYSG$6%u-{+m`#iqzWnhMblW|M52(<uX<{!LYS}(P&~w~ns(&~2="
    "A;tMUfCPy&Kl`D@P@JehRkCoU!2edSe4=+-B|c5&e5e+B?FH?YIS4Z)_ng+eM{u0{41Y9&sPj4^dWi4c+>uYNDzm"
    "I0C6rAK{E$)n&ipY|s}-j^^PO6^L&%x~hH8$a@0G>7AX%MFk@J%?<4f3Ke&EcYpTtL`6tOaPv4|SX3argYAPAk1u"
    "awp4Ti~bUsh|8`MmUyS+q_h||@xl_hA=lL+?jcKYA%|LINP6Ylt$|FHZ5)fJUbS7>*d>hZ;u$oi_ss$NtgXLs1k#"
    "8uDYN~C?{{vwM+xRvhrQ6!@M;cel=&E9(w5xW75@o(qiDumked^w9s-fVia$SQ;xXZ92lYnxrqZ(8&e^3ua8ShYz"
    "bb1_&Iht)4onJJ#H-bYbLZQzo?l2m4u>z5C`r6y|SD<o&WK5MG-f>R<jngN?lDU#<!rG=$LX07Fc14)V8&J)F0N+"
    "dSW5S?t95G&lT1vNm6TOy}d9d+O}Nr{|(wDtTPKa!Nl>8*ZlxVa@=b!|(k54gSbDj+!O9ks?@B?NagjYd{sz?II5"
    "rvn$agp|P^bd(K*s#-VwqW2J_zD`^<ia$@?p59Ea4|qT>LoAOkLWS+t-m3DSGxml`Ig3c>xKZ6{QGs}T$z%~K+0)"
    "QHdKCzVXJvU(7TMH>I!-JC(cFx#qX^`4;;A|ofp~hoZ|tHXA=FwLjCqycB<15`qDZ83Y4wdBN^qonv2PKRU`rycv"
    ")!9^QCX(v;h6?jxp}#75prNlBEPYrWg-@d{C3pDl9fo0r*(K%2g#Xd)8E3|wcb$3P`6io8&=M$>fTWA&>Q?2MjjG"
    "EqZ`HZijH>_gkw8MH5-I3uI>2xVyPWj`I}__G1z+u47RFxr0bn+CS3T_!`1^NK3g|@zxllN#$$3F!^w<Gs~$I2uP"
    "~9Kp&gIxkYP*pal5S3#K<&wBUHMF>v{~up9<#{l;xa13~^H+(4+N6Aj7NiMj*nLJN7JMn>_I$Sb@NfbRT2|GCKA~"
    "kBdqqGrw<9q)49DM9s2SiF}&Q^?%GTa+d?PWK!C!@0SEeBB8_71uK!!zBwG4YNA!Jl`oN4Z(9Ay_k5x&kzCrdLwY"
    "npPt)^{FZU`a%I=(_kl?^Qz9F4nq-SaA4P{Zt@5(bqEDDJY7u%1ED&*ywjB^x)#B4`nMi!NnES_*<QOL*W;TA<99"
    "r{vZQH6}C-?eD@&CBSSi}cDbk<;sj-{2<cY2DLn-D&Fe1V=!)*5}>SA9;mg@$nd=b*Hr}M?tu$%-5BBJ<jNtkmQE"
    "p)be`WU~ug9b!U3&Ew4B3A?;#xA7u-nbJL!pJRpId+kCH&7;O5n=6R;YT~&Yg^y+jS&zN{eAj7LMrzj#pH}`D9Xc"
    "4yrQatd7O)MgT#}gzh0@=|=GVAea9e#kik#06T>EH;2_-tGa=sT<{Um(vzKhdJOSAjr#zii@FB1(PX)m5)jB(P|X"
    "m_;H;b36ts5u6+D^|VG699bq;L@R+T65&;KQ=RCf(UZt*u-?e+i&Awu@cPHfm&mG}I;uCl%EzSGQ+Z}lNQzq>vMM"
    "cZtJzc~lh=9IjEgEH<$AsCSl`y3N>~{`YZe@Zy#6)KjTH6w7gr&%tEP!f7L`yl-l(KZ(cO|=)sI^m1`<FP0in6%&"
    "%dt=KIciu8@L0`q9F9)>!EI_tr&w>;=Z+OLWY&I!SK~RA?~pS?;aAy-cAEgjV<mrJ%x$#fT0s#oL3~Xcl|mlKfzg"
    "5TU)Bnj=>59=UNf&L9z<@@|G7BNUY_)EsH={SJymriwb1*Mt8*z#XMsbKIp65FHQUfs;ezc7t{EdMQoGHps5@dfz"
    "&QM{ACdcZPX_dMIx|whCeQxKQg@Y6X0PR>Z&b|41$%&&$NDBIXDstj_%E+eob&BQXJ=UXnai=T!}0X&B3QcPa-^8"
    "w&s+@mD}`6y79Jh<ipD=xvd<DFrRw*!~rX>Esu5QRid@0k|H=-Zqis4BHT^4U=_j}_$xyemAtF|J1edj5f~SEvI;"
    "@X<H{%s0bP9C;Z-4?oxKH{R9d>23tyOxivFr|_rMcIT@(SKv+byR>s3PVN8L?4vG_4~3KG6EyWVFUqFX}BlkT}*W"
    "!*sVmAhZU#d@FY$;-#EYCxAY@$xUpLlUA!<>Q2_lyt7?$n$;LI|3oSH<!`)ZySci7s%_EYP6hVgC`K$&u$PAKDda"
    "kKyGhM6>|2`6$q|&U6<RU0?ECbe=R~!@{5pHtooKn)3*Cy1>&4rH}^X=ZpHt8|F8S!+c?ff!WYeNs#o!tK%|Q73;"
    "vXhD_e=2lMg~9@*PZNc`)l8iFD@*V!x<V$*~Vqn!QRSO4U=nawIbC8h#hNN(4ApqI~q|$!(g^jg1L8!IubdG<5qc"
    "67h|FbBUsmo2IsstU_joxqtMmTW}R}+w+KqMIp6eoc8<;K=f3ZQm4k)tJ)-Y)Ssg$q_&%eTNIV>YG_2xq8^g+y)3"
    "fN3F*SS-zmZ8r|`V4YQab9^gY|2zsy`*0V%_@`)I0h?MY0i8q-lt9X$mJzutX2H&vHAm`8u)Wd`~t-RlN}nrmT_d"
    "kD=RCh_+WRq(cua5VPV>kD<aSN;Pe)y>=h-qzkDBwT5KvI4p7Or?2MHF^TEJ-IiPD{Jovr1o9kaQxsMfzaOTaq9Q"
    "}<I&&>#5XTc`O)d(3Z!`8&-z#dVyyVXD;9wSKe!PFpMDIUKzzTMeHU`Bi!YGjhkEM6fubvs=KIOB8oVQs<*U0VT7"
    "|niL*2(^>xs)2e&g{-^PlEG-x35zCiHq*;b4)Q7cpA#8?9dgT>S#oAU*4zKR2C+7ZNcZnvVasKyV~NY|X%5zywDk"
    "zM5y~SzPV+&;JAeG|(a"
)


def _rows() -> list[list[object]]:
    compressed = base64.b85decode("".join(_SEQUENCE_DATA))
    return json.loads(zlib.decompress(compressed))


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def _remove_old_vocabulary() -> None:
    op.execute(
        sa.text("""
        DELETE FROM vocabulary_practice_sessions
        WHERE curriculum_node_id IN (
            SELECT id FROM curriculum_nodes WHERE source_id = CAST(:source_id AS uuid)
        )
    """).bindparams(source_id=SOURCE_ID)
    )
    op.execute(
        sa.text("""
        DELETE FROM review_schedules WHERE item_type = 'vocabulary' AND item_id IN (
            SELECT vocabulary_item_id FROM vocabulary_item_sources
            WHERE source_version_id = :source_id
        )
    """).bindparams(source_id=SOURCE_ID)
    )
    op.execute(
        sa.text("""
        DELETE FROM vocabulary_items WHERE id IN (
            SELECT vocabulary_item_id FROM vocabulary_item_sources
            WHERE source_version_id = :source_id
        )
    """).bindparams(source_id=SOURCE_ID)
    )
    op.execute(
        sa.text("""
        DELETE FROM knowledge_points
        WHERE source_id = CAST(:source_id AS uuid) AND type = 'vocabulary'
    """).bindparams(source_id=SOURCE_ID)
    )


def upgrade() -> None:
    _remove_old_vocabulary()
    for unit, expression, canonical, unit_order in _rows():
        unit_slug = unit.casefold().replace(" ", "-")
        key = f"vocabulary.sequence.{unit_slug}.{unit_order}.{_slug(canonical)}"
        content = {
            "origin": "unit_wordlist_sequence_parser",
            "role": "unit_wordlist",
            "lemma": canonical,
            "unit_order": unit_order,
            "dictionary_status": "pending",
        }
        op.execute(
            sa.text("""
            INSERT INTO knowledge_points
              (id, source_id, curriculum_node_id, canonical_key, type, title, summary,
               source_page, difficulty, status, content)
            VALUES
              (CAST(:id AS uuid), CAST(:source_id AS uuid), CAST(:node_id AS uuid),
               :key, 'vocabulary', :title, :summary, 'Words and Expressions', 0.2,
               'published', CAST(:content AS jsonb))
        """).bindparams(
                id=str(uuid.uuid5(uuid.UUID(SOURCE_ID), key)),
                source_id=SOURCE_ID,
                node_id=NODE_IDS[unit],
                key=key,
                title=expression,
                summary=f"{unit} 单元词表第 {unit_order} 个词条。",
                content=json.dumps(content, ensure_ascii=False),
            )
        )
    _refresh_counts()


def _refresh_counts() -> None:
    op.execute(
        sa.text("""
        UPDATE knowledge_sources SET knowledge_count = (
            SELECT count(*) FROM knowledge_points WHERE source_id = CAST(:source_id AS uuid)
        ), metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object(
            'unit_wordlist_entries', (SELECT count(*) FROM knowledge_points
                WHERE source_id = CAST(:source_id AS uuid) AND type = 'vocabulary'),
            'vocabulary_parser', 'unit-sequence-v1',
            'dictionary_enrichment', 'free_dictionary_api+mymemory'
        ) WHERE id = CAST(:source_id AS uuid)
    """).bindparams(source_id=SOURCE_ID)
    )


def downgrade() -> None:
    _remove_old_vocabulary()
    _refresh_counts()
