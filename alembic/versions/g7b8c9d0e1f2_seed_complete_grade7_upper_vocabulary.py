"""seed complete grade 7 upper unit vocabulary

Revision ID: g7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-06-19 17:10:00.000000
"""

import base64
import json
import re
import uuid
import zlib
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "g7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "f6a7b8c9d0e1"
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

_VOCABULARY_DATA = (
    "c-p0X`BNK7mjAy}+p)1R6Vc;t8=rJcd_}isrq#P{j|0QT_Qu9HN~na&DwVWVC1{&pIE;<VCEM5-Bb&oqJ`nh5TZr"
    "p_nNgKWKlQ(`neV+Sgb=F4j=)fooS%I8GV|rT^69_-`>S?KHY~-EI&{^NPJi|FSKX;pl>PapyCeDy`)e=nR-WEw5"
    "AFQJ-ju;Vl%qFJef9OXr!HOmpRXH0BvXd2>fIbAdA0Qq#vk?Y&m7B{e(B7t{k}6>F5a`pN9sWJW{`hlR7r&UFJFD"
    "FXEY7)IMVX&?>hq?SUPUVrb7RN!JTOc7gsrPaXHM%`h91lGPPDNO*q+y&giUtf9Lm|tUb*MwI2`GQK{+-sOjkAil"
    "(IiKBR>@cn9U(c_8w$;N%#4si#sphiq$&Ss^{ss(<sf^i3aoHsA&Cqc}<|Z8-@`eRQ9x2z0>I7Gb6;J&HH&YHN=-"
    "=QB^)9PzOaj<e?z6G)&3a}Ic)LtZ@9i<1s>;`C2A^Pf0fD}&|TM|E_`(VnJrVkkHpY;Auhh1hR^e6mpo(-h=pD#J"
    "l;WLjyB@QtxMU*3LGhmtl@P5Ja=s#jtZNeuA+`LhU1&dyE$zB6|+HibD+xG|iO`(9f)5;2q>Rkl=Eh(RRDNsiK&{"
    "0z3lR2`Tblf$sE?SW;x^ohwJ#-7UF#DP3&5tc_*T-FmN2fg0+bHW6oZqK=!iwu(eW<Pa!v@4~5lbVk5>c4Z$P)9-"
    "mcG-n&<@QHsdfpkBIfieXP=*??yng(i<0@gRU5co!B%-PhhbwQU+<O~LI8_$jRJUPn&K&8(o889HKV0U}rrIh+5!"
    "oKjR%V|tMmYQZ?Ae}rTgl%29OUo6|A9j@g4vH`BDy>J)}Gz9xAvU}>-O*)d$RaB&~2L91#6;D3&ZTW*}Zac*Llo%"
    "!6emtJ2%dl;-3IUDy<m*Ur%L%X--9e=4%lyPa|!u5sqGcH*Sv(!Kv`+v!Q=b_2^CDby$z8K=j_MyZ`D7DZVUgz=^"
    "05)^Lk{us5f^kk-E#Y8R|HBb<OWF*j7bJ7y1$ej)B(4Yu!KFB@#%0rJkYJ-qql$bU0rToK)df=j}g->J@iDi@!9A"
    "%lNZGzE@Yc8rHW06D*XD(|d(0W4qcy>Z#%sJ+)LzSMf#S}l<J+x_J&IJM8!$$O9z$4WI0se(ic->Q+Z=LBTz84!r"
    "r_%dy${TVI^_h-t*SB+?CMg;H*B{gG_yRcSSDwTKlnL_1mth;Od|Lh-dp5>g!GnMr$W1Yl4;OE@-@{x{|bhD2BqI"
    "YYm8He6}?$*NXBwkoAz$l45vo*k07akS(5girh>L=@~fI&%qcX*ug;Q*kI7I>C&pro7zCAcpQi$A|<&+gTYyD1@E"
    "8EBvAg!ay}4SPLzlJ-VMQw)w^WLh;(O|dsi{3xAef}?a2ur%%q_J^aevxuQoA1tzmlc1!SOz4KKd(B{y@fW@uuD0"
    "SMALGlJ6OQqQ+?7yZZ$*FUON3!t*-KkY#<&Zw`9SB^nZoEUyf_JHLIK&Gz*DUHVA&p<IZ6Bf&8QmCl;{m>K$5%on"
    "hlKWo27e|-Ipf;Qvr!aRv0?r4wX@tU}`GuQCVlEgU(*--|!77`R0#3{>XW>X-{tO-??#jW8BU%aW{sWT5|HQoY_5"
    "RGG~wA9?O=C{j71hRAQUFTpDG+E7_MMA8RON1T_~%C>k&K!3e8^FZjY5d~tGNWTu(v1!pdMfJHjBX0J~>8{^LC4p"
    "(tTckDYbj~4_5Wm;2Uo3mxFsjasTS&MdI(b=40o7&y@Bsp&fosq|O?xp=8$GOVhtLvw^rN=w_`TI7QE1he7lH%K@"
    "OzEB7<tFLy8hfa06e_tPdwjCI1J=~}6DU)>m%qbkNckJcySpoPo(lwgF7J+i4rl_bKBfmt(O(F9d<c&DS*G?mkC!"
    "}9WXADeTxae|X(<Eco-ec*AO0-y4>AVhM0GLmX5VqlO9Fd{V;TxLHP|0m7o|nkp7R#gaUBpT=}qx&aw8w?$r}n;`"
    "PJ>)3{?6ORHn_KknJ{9H0vwd`(H?DM9aVeW`9v7fB5W+5t+zE$i4)Q{Qeh0_Qq8UsO*(d&Q)f1zYsE=G190jr(3w"
    "4o<@oA;q{k}-bnSr97PPd0~N#<k7_X`u6-=!zOWlB4zyoZzmqP5<aWmH+MnK`_+_HTdGfHjc!$XV3B@s!!t7lpg_"
    "#Hj{q(eu0OnokxR7;pj8rBz?fe>O2n8np0qcyAXM|&!ib4h^VCC+(t6ZErPbS!m)?+nA>XL!W34T;1P!o5DxD$=!"
    "UM)~E6_quqIbkwdV<=YLjSqa53hz!tQW7ANzH`KLjGhrYqBul5NO+S(n!UNirq#)hyDx?r7*oh9^8;McZ%*2ipFH"
    "?)PauqWA6KA{WI!L~;`$f#@gLBK7Br5f)i3Cy<F8kFFVc++I}KwJ`BIDHY%x_|Ja-qyyrq6p;2(at-s!nP_&<yN>"
    "%kSvxiY)Ue=ij(Q@^>ZckIbckxqOAQkRpk1#~40Q@}JSri1W<FgIRV<ygn~ybln_+o8*7o|U(k`0l=)wfA46abp+"
    "q>>cFmv2OVT_ZN7htxW58k_Do~E*43JnV7S87wvn@RvRyGjr!`I#PmIPW0^iEmKf9R!c%)^@=$+`$DdSC8&9fe;#"
    "LRlx~l^qPm0z4#lsZ$G^W=h7)HM}$45Ll!hbKlsvmJfgquuFfU_B*59D4&)}e>>2<z(ht&eoYJOzUZ*Xe%C@0m8w"
    "m-^~MXLFLPeyb1pOaliczDU`AcrszXd}`-b_)cIAUc9D0kM|qY1Sr5jk7K{(?Z-&*nP7@#9W<RjJ<3&ljNv>O^I7"
    "Qjj~&M8O6d((O&l%9c#FqEdwENkh?|Oux{*oV30k+48)*5TX`&bVASNDx?W9mHZ;ADdt>Uzww;zkO(qYZ%zL4RE*"
    "1H8KpM`MMI67GB&cP!-ni@3N13G$pbkEyU1A7#$0n9DM0J3g{Lk6RaLEQ=)q;1ZAWWUeWh>}dQ5kv~T>Ajs4CF&P"
    "yW%VA~f~7IBR&fK5|LcY)O|wD`W3*pm{(iM*XT@5oJzlh+2T7e0YG<myqH`9*0rv2^STi1uLOr5~7&;`>P*J<%7J"
    "2ot!`DLXbc%-P6b&hFJrkP>MN`sontb*m91Eec$`7@TXIvb^gOe}S;WeZplZ>D^&^wb6-;u<Qc7Dvya(}`4v;dAz"
    "(HBwUkL?@yEqT;=t~!o{v=LZCXI;$_GEA777>GI(?T<HaaIc&TJYJ!_gvUOTfJZ(xZr-^jW8Yd^s|m6~>q7#Ze7~"
    "KWK(XoMU)!5|D13wI;gE;PS$!x(OUzIeJUn8Cf+vTQAGIe(4|m&ePJW21I(V9_cD7PO2db3UbMTRuRHIQe*plI>M"
    "hMmE4{Y4bRFd!od-r@G2h6T`Dus@qM5Yy>?DZ9Ae&KNIh66z=BoD%iiLWyNet?ZUW6uQBoST0mhH!@nGQ`eh?X`S"
    "eAVE+c_({?An+T`q5KgL0j@v7R&qMqEhz)BOhn)O0M_YY(BB(YE?X*6MmhjLVL`!PJJAzo(QxG<`t|j?Su-aNNe*"
    "AXHUcFO?ct#BIikeW!W=mkCW8`S?Nf7HN@_KMLGrHq9KO5_cY@jWvgbbArHmMjms}oGy*sYsY;lXO;?oWn&$64j="
    "dwcXj?ZgVA{fDYYVF7DlJsLu5{=K`m_j$DaB%|PG%NGx_N}>Prkp6bWN9N4$IL{BQT|tS{o>VP}D4EIdbv)7D*&B"
    "B#u6zP8a6YT1h1@s8rsbcJtKjor;kxUECZY$TMJbDv?qug>KdFQnV5N6}F~WWXU}CZd6KiYraVjGp5vMXzWIqBpX"
    "_=h@7KVJ7`l-Y5#JIqp5Rh?+k;i=rrFQ~=5yKx~#5fqCJq)G+<f#NfbQ{dPIp9;b(Wlq&iqG28W1b(e{1^zEwU<A"
    "#AFv!B+b{3%ht*~FBihvgFL_tB{H*N@Siu<kiTzMt!*8%J_Ks*@2mI!J)$m-x*FNK^L*l)JJ=VP|v`&($22v>2mk"
    "enthL?a@g^zY=T>!$0r!YElIn;5Bf;Z*T?BSM;EG`U*W0oAbr8fs4F3jWM<x)uuA{EC393cH69MF&M9d6p#yhP#^"
    "BAy~UJOD0AJZlWByNv!sW@dsk+xln!fL$2kTLRL!E()-LVphHAO|z#rVBPN8xz)n}$B!f~qY)JE>%o}8q&>+!PW)"
    "lw&S8|EMgUQCjz(!P#eRF~CD^_F&h#<|n%QOV90qDQm>(G>k}UBYQi*~3S$h~ltSmosZtpYZxchhQy=nAlVIJSbr"
    "uq~}kDD0AK=11x{tTV4H~%QvcgEe-0a0d|m`Q1(L2TdN$9OaN_nHl@E0r-Z+ab|;3){{Qg6tY$vWw6A>OJ;bVzS-"
    "~0xYZ@{Tx3Q>5zniFA&;VPb_x=`$(e3l|+pzNg5Xf+me|i_gi_VP9T(=LE+Wbic+f&rIo#UpG5KM8a_znoeg^H<w"
    "tyQM~2yhFjJB~Q<6uS5-9is`-sY51V#HWR_L9Vf$cJS7uqkKKPO->vti*B*^^WFz=n<w65|Vfwz|e1#OTU&$4SSC"
    "UTr<lF_;o{dtU^Bon<H}!qAq@Qao(bI5xMJ%iE)s?QzMO%V9u?Jzz|q2}gVLt@8w=Q+|!Ttls5bq0`O1v1icgM;A"
    "1+`YjaJmEl!PGdz7dfaFvRaz%Q+lR`b5;7)wv!+!g`T$<n~-ds+qqgDbI55M>SL*3_fJ=Y~4`JL;^ujt295+-@@M"
    "ww777hfHU_DRmfGW*1Nwp<(WJAJxo#P5JTYL}J4c}a&8R=cmU0gpJlXZI>o+ak>BRt-2yy1|p7d5dHHrAXsw3WE6"
    "2Yu%jBY=LzH6{FK4joW1nbqTW%H3>Jj=1yemRQ!u#s`S6h7z|E$&a%53mF(8%Vf|gs087$W(GgJIe^%L@uCv+%uv"
    "#z!s!P=<3CaXG%*y2)YH7kDh#RL;7&Pxlpd)WZq?N*tMA-3RLkZvVwk>~Qh78P@TBtlNh*9t>X1gX#N_R!)XQl8K"
    "!ZQy<K#&I#VBy)0EMU#Kr|R)td-zig)bVF}i|?q3$lboLCeqhU+_A@oMd*pL-J_;-vZtfrM0-d_lNz7NuI9;1!$r"
    "QC)~DHn2=Xx@nA0uIbvg(Xlh-y$URys_EYg?>Y4afRa_dm&MWns*YgYyp+i=26+{mDEYfsF%o5P^o?>YngzQgIWO"
    "|(K7g+g&WIw8V5-c{IR<~G|kcsHOHqd7fNjX(0<`|8U*e(Z02Lb5!h=BowL_`NLt#!38vW3m*vi!3@zZ9NdSF4N4"
    "4BjC%PVGngs4aX%%QW-cMLJ_%xocjF0f$V<CURte`R*taf=sClo{xdFH65vUvPMz{Eakv|c)#-xsal{$e;HTGQ&c"
    "0i+w@YrJz)zlk^slfVr+<Q(OmLTF4&SN0_#wbn9xOEvqNTTv50?r|b}UsB$oWo+dHm%;<kB6mNqDZYy|E?88klr`"
    "wMAmkoI3|T*%A)d?H|L109R;67`b%*1`j>1Xlcsz#thwJ!M?{WA7}CddpNS78Xe&+Xv1}-aJ#U_L<j@_lhe+dMR$"
    "MVDEAuptvSqpr858MpD`4P@cgmbBd;;r@SpvIVk3*N&muBfmJxPVMCkZ)UOcGec*yGX`GDo!D_dQ0N?C9Ba@H~Hd"
    "V!}0IoVP6AcDk(lFpFc%6OAzBFWcX-NHhpFzrAFB9GkMzAu8<O*t0blw;u(i_XX-<gn-LdqCaBl>6JP5Op$q_Duq"
    "Ab78!Ee1WvnpvK|L61Jy#T3@M5&9Ua3l+x?+_O81z;Ndi%Fg;}{o{FF|J(<)5e&wgI>Ez#tP-D>TJA<y?jXZG1go"
    "Z&UFde?`BIIr2`5V-<_5uL23vf%4X>cKUduwXMptD=j<Z#3we>gnT+0FD{rVmtC?$lv6mda)Vtxz)oR;Y=7|BX-1"
    "+d)1nD+Bl-p>VB(>^TOK3!Zub<YPJm@8MyD$+mK7grv`fz$uTZ6m4T#Le#rJv47W|*tT~j|Jgr4&m(u3^1?dL=uw"
    "IN-wyVFx%79kd-ljC7?<}e6PqFfF-b<5ok{ZZluNUG0Ng&BmGIt)lh4w-`7BAU3xSfWOOs90NTD|&!GoDbrWJe&3"
    "9S#G`GRC;Yhg)b7L`9GWz@9Q)+AkZ0<VO^--ony#%wz7*!ZV@v)6Og!9sZ(JR(zT>>c)!eN^oq;L*d{{~<KzaI#}"
    "YI=3JvbLG9++R$=kJ?l(=#G5WK9b;K$uyMA{Z#m-yw35;Gw3lx4TQGAu)}T85LE=aG^hbMSyJn>XY?Ce$<p~nwxY"
    "%&~Tp7zgMA}4#rllz4e2pT`5PBvr3S@jq?7t}N1Fkx<CE%|~o_RemZ7;nA-{2y95a}<O!Tyq+*p0nETwU0%Yk4$-"
    "vnHj~!i)>cb51T#qjS>EZs0>@8`kN?AlV=>5Q%#fJQbojR`c!KrelD&kD|MUM$z4~VwUAkskn~ev1@R(JNio-<$s"
    "q}D*K!D;nWLasF&p)HA;@%o^X`z3s$y2)Z+=*zo5N%{-a*SGemn8gCxKG@D&sL5F_8jXO4WSsdtEjT5?3AER}Esb"
    "(DoM^2uImGNHU}1he`hnALBW?g=$wr)(G9>R_jAf-VrUBgT0SK05X=mlr`YQ!!WpW~d{EIoj`Ln8*=n+7*{ov_jf"
    "_Ub08D=$D2C$B(XTTr#v^{4=;*tmj4};c^!ImQhsBI`ydUQ#^nf6@>9L-~^s7;0>E)zu9`=(cN#GhzYN`<fqks#d"
    "BQ;x6rQ%ZI9oKymeH;bD#h9W^-YzuHS|{wBjmSmA?;6h0(5b3rozp;M5Pj=fC@(x&1>TWAIKu|G*pB$D9=bDimA~"
    "m;L2%8COHY&=MtLe%st2I}5QP3qwOFdyBicv;ql=E9eD})81MV8pcgUj$`6y=y2jE*n73j8wY4OM#8&~K(6As<?6"
    "sgzAsDsG69D<9W)JcR88S^pKw$~7-#BZb?!YH8qV~5rL@mg0=SsYA<qQuS1pCv9|`SR0`;1<R&+wJL;b;=2!<u6J"
    "wXT7X640zU4)?J?juH<|7;IUvS$&*v?kxgt((@Au%9yUVBMM8!(2Kcq9hN8GU$M=BPh)`AUnVn4P!}Bje<#-#pSF"
    "m*w04=hodXrXh51(UpyBa2lOuy0y!q3@!{^955iLM&b}pw@y@>U=!5fNfLtM^N9>1b#m=(@+J7xg6=OJT&_xvKw7"
    "!!fA=F@Y?@%^zOY<yjknoro3%2RklHB3X@yPuHG0+k$29zGfxaptYN{^u)oZ<Ki&+(<(?1v6<e8}A{7hl==P3Q5}"
    "ks&wSeX`ao-voyeQ&xKwx}e^_eRR+b0M0=m0wg)VuMqVvtwKI#mS1{U-K2Y}yNgUEm7*!dWcpI)Ep8OanO`M|YWY"
    "0B?Tq9kJGa7bE=(@l55_8w?=y>!J;QCsr~LO8&s#ZjuFl8PkgA#>`*%_tLr|2*eXfZ-ItNZiT}Nj!dqQoavU?x>F"
    "lU-&R-OafoV+-s`U^Hot9tjJ(kXNZq{Ba_ul)@9JM5{g^=CXHAC$Kq3R8jW7>^Ow$a%s2{rq8cTm-;Ob#+mC)U|}"
    "S@=PW}YZ7XBwGgl}+>h@C=|WfunM8JZW0d1}KL4~QrD@7dkJmldG!^*GXzXcgr5Aj{Cmskh%uFbjKY83A5w<+cNT"
    "2_Ta}#d#ihxqmNu27<JlXeaN}V|$bhPsJ8k$m?LhkATw@`$8a4+j18ZP4uEa6V`J1OK{VCz++x}X5&z0_hg5=lhN"
    "Kl*1(>CX~-k~lccU*RR<aA$6@-~H_q<p-V*oW*XC9Nm-<G_lRc_S>e&*m}{f!C1%1hC#tfje?c#{v2t%%@dVTreL"
    "I}?-my+-W4M*X&6^)MV?eE^EjjPS&>n7<9v71d^00{k}H$^x)M9!xq^=AV|&v_Np1{iD6-|%T|rT>H({^L&<VLS$"
    "HN|YC|w8~J=Z$C(;gk>gZ907NMYm7TSlel&IKwf6EEHV@jB?9#zG;3o;4G^WsrLPhOHxRj4bam^-2T;c9CLQ<Wmj"
    "nmJu>7@~q~WaCt!ky%;#qNXqlfMtG?Ugm|}r5Rmo8FZkILV|M?FFlY?wn0yn%JSLwah}rCOxc%4Vt(=!Uzm;Pj^Q"
    "ne+#d?UUv6$MG!9o_%a4eh%VJ!=LcC-3)Pnc3e(d1u!*R<A`Fp&lB?zZ!6ua*T|;d~|ze0+$)dB5iJobg$Ab+D2j"
    "t%GYg-*_dI-v#aQBc6Yj_+678)l^fu1lMSK!oOhI47?mlQH#|(q@`XwTJlRjmU4-ANh)`K6mdL|=5o%Y_=idHkIH"
    "P(&W#b@E(P*UOQ9;Gbz;8Y$Xhr^^6a4wpmE3xMnI|4z2VDWOTCmn{a}n-viUVna?eU!)ZjHbaF*8f(8!wrLrkX(^"
    "!ueDmPo4eLwE2UN`*R{hD0)}I*CSgl3%0ulG}Ll=Am;-Ixc_nFr|$TfRv7zFQE>dl4vJi!HOO}G8+vSo<?^RG`gd"
    "}Cc=5Mc>IhsfKX)fCOXS+Q5x@-^W-7ztm3%)VavWZE4)0QCZu0&l2o<6m>;wIHwmm2>A**{y=><u1Sb|k1%8;o3l"
    "ZRrmi0<$74ic1L}nL|l3uP5M@#ZUi4c=s@(|k?lk4oay}lxX`n^gj8x>gFm^xZu4ONlm4%73X1nM$6i6bGsjb8)e"
    "%3nw)mvMDv#(l)`TAHO-od-oB8Oa#kbS1Yh8G+o8Zr>Vwo3-Z`Fk%;oWu+L;@Oo#68R-^YEM?D(VW>H|%lnnmqBF"
    "NI0;hH<f9hgtK@#gmno`10(feiJ+2ln9!4Vt?W6ByjoXkEg6eVY>Gb+R#(=z1Vh+<$Ik-fUw8lgBMzVMQO#<T9kL"
    "lMNZA{%t`f!2STe6x#dBJGo^mY|C`7{<-=j8u`9?Cd~3M5tCx_1U7}#70!Zic=~#E|BY#(OsFEbEbLjYs;AcjHs&"
    "XlwlgyYfLkK18$rvj#Pg&H$>@=&iae$QceWAS5XqAWTTwB4}tn8b54Fvq&+xlCCa*?VzA(uMHg-5!=i_B{NZ^XQd"
    "F?OaV*n{41O_(g(LzgFey#5y~A4-?H%Yg*?m~K&0`1d;D%jzN)e^P(>l-w2f%r+e(RCspSo<HqscyEqdgECbut6g"
    "8(*$)o1#{T1hJw=VMc`)x#>}&zgQs*-ndh5+{wHMM9j!wWi$4G_v4+-56*L;wuX0|+Ms$tY#CM-3V7mG`v>`iz;S"
    "n&{Wlt6$!V$+)Q2U4+|eyTDwrOjqk5rxmtUZmqrjXi-JlLDm~b)66E3R71@^$3w*>UtB^w477)bOP=u~uv7Tnx3d"
    "ps}F-k<^_1{E0LM%!B+>0rOB%j-fU#MQ0@j^1hyC&*jNMlhHaX>O({Zsx_EcOJ3D?rz+63p`J|I$fwPKH=eJpQQo"
    "5QcrXyVsxRJy-37DbeDSiC6iI$_<u>`I~zctmeJ9)&^mQADVX>pL3cLrIKsojwAxzz($Eu3(2=-%0$cZ7016q}R7"
    "J%G2T@BiPviLpmx-Y2IN4U)3(oCHJHJ_nbIbyb%Mq0#M-kj&<*j*VXhVebxFTy-oLp7fb@fmg=Of)WoJ%&9lu*vJ"
    "3A&tC$<MKEE<A$&&2Z}-L!^mb_S}v)lyPy1jH6f9sc5V2Rc*yfE!BL#yE1?QLiQjsGZBTVBY!PL$VzzPjO0X`#&9"
    "LX(D&*NE>nfm!DV;ou@FZuKpF-v=wv5l@fC{p(o-<dmR75GC*iKlQ+tz#uUjqzRipJ``QgQ(4=1jESZ7D7GyTy&x"
    "DdMf;4K|o&9kE}pl3Hh?qbhXjN!m_cQIc_quz+J>whxiD%y~|z*BpRZ$@5s2A14~*FGJ`R)#$wCeEx;uv*&D8U?x"
    "ehqQL;j}oWo#gYg`W-r^+<OJ_ktb;4Qvsj)q5Wq508I#h(na<k*_W^DlkizJ|@NO_E@f4~uc>A&n5whS`31X<3IN"
    "+xHVn(pjXiC#iG)Av!U<*atS~a}JU=I)ZwJzZr-Mx8dbf2G0>sem)^672&!>U~zu*V;jcX^Se%9|B?@>983`d75c"
    "0(+0B=z<G(duJYorfX`HwOkC`M$F)(8ly>a-`ks$gj7?tO#~@U9**_{2M1eAROx=MAPl5Ylt;r5k9HN~JJm<~!Vt"
    "a8CIms*+mS>m$rqHw-d1!b_rghb!2eOgs#kT04SD^8tV>~ur&S;NRsv__zB{yQ7YokdnxCTHaxqXA=n5wK=qjn~A"
    "b;x!>1oUxOsUl<oi@)kE%uw+FcaG%2x&^xIbsTO6@PM!bbZKg2xN;TC%g;*%2L@Z7e}EoErfC=AB#}*qk>=dz`yj"
    "t&qn3Br@Ql*A1=UAi*z^CT<vivmGf=WvO>HW_l9E2FnbDljj60uaC?g>Cg^*FC$Blyml9~s1v-^~xQ-HtYCr%HSu"
    "vED8uLJ6;h0nlfz_h~_`vNC!cf9B2vpZeh!eVXlQ^MUD%IH%o(W(D=1qH?po&|<5LXPUZFf+v!Y^>gy<LY3+(|VR"
    "?y~kU`+t1%o)swVasl&a_<eiy)P*`O-}+kOe{0XKg%?g9>Z3s!Ne{c}ab%^?AUCap!eNi@*rjQa){)H3nhWJjWns"
    "G!(*HK=S~uK;CVdfuN!iJj>{faEQ+2A}o`U3GX1Y%mga+Z&tR|Hm8gg^chZ=t@LJ%EGUZ6VLkNMkBfqAVuw1#KF+"
    "0%h%0nZdctDe&D_xQc2>a*u|v3LZbvB>lc%(UT`u>9oA?+DFG3TNdiIj%n8?bX0`vcv^-U2^Z_n7>4im4+8Fu@z5"
    "0#rq-y$`#3OxL9NZ3sdm4?S5WB{A}|qmWz;(q+6tL>(?<v2lvbJBjxSgItaZHz)!NC@vb%g(x>0ZkV_L^(B$wE4f"
    "zodE<lszsDD)=h6fwt&xFdJ4?s&}Cj-4A8)RI7#ft_86GbOOX=CdK*07|6(?&?6I)Eo7g$gT$sT|<Rn*WsX>J-uU"
    "YT3i<Cq>X`&N7-z^)!Y~$cRig<;-7g?Is@vJ6KKz(ypW}#Vgxq;tT&a-qy2|fnDvgQUrA^VTC#(Axt^OXM+yElVS"
    "dx>hbB*LmfRe^r1>|GPui1mk$>Wn{{X>UD0tlokj;nUm7z3Ys&9dUq7*jKafCeey#5!6h&cJlINZOmxDru+$oO%c"
    "`Sl*_H3Y}N@-DyHENjGu=T<1r~E``dR3exX0<aYFxu%Jsh@bwEOllQZGEVeUL9O1y*qEe8-N>}b7F+1Wl~SlZ3o("
    "kJMa{%cb`2QApF`DP;q@`VT~7IHZ`y5c=lXV-RL5m%3UeSAyE=kMwhooO*ObZSI?pcYO3EJb=2VYTt|(QhI-xad`"
    "he_Xs2<~O}*BnnFhDkRXVtM%~8K^tUD?&aHiK2>G0@x@2mMj7)&Epd=&N~bif2pM;5?Qa1rpo_)Siu)mPkNb6)g2"
    "b37h)_I$uPv<x+k-WJT+cBY4&Vi9)RunQLq0wH9>@>6)xVUjI5`3?L!JNCdaE(Bo2xGS?q*6`Fet#FTb4Xir%p2-"
    "h>ziedE&T?;wL|@Lb^VHdya__;d$9sbq{|oFWN`cR)Um+%n6=KSzca@R1Bw#KC3K-MMM5&sYY2C=QM$v=H-iF7oy"
    "t}d@H1WV6I5@6j-cY%icbE4eBYV^t8Ww_33@j}PyD{li1kDTeAIV^LMI=nw75g)l#W7Fl&O1-<3bVyhF>%L|>Ebf"
    "n2oxcrwz3vS5ihNE_Clbzw7kUdBezd@Y=+-s<dGP>(slM?Q`PqpIIMe827RGNObPddjIia09QlVC{wXill-=T2+a"
    "b?|XR7@{s{I-Z>5sg-OTkriE<tQIazp9D1=ksg{t{03t8Dc?-)pP)E3<_<z{W^js-mO)V#?u=j=3qT_c4DYu=(Fl"
    "{pA#W#g0^yNS2P@G}SIylay$t3v$Ew9))}+4>c%p>=It4#P8}$^1>eIMM4n(rfbfbeJ4U>QYPD^@A^T(FZQ0v<G{"
    "R{v(Qj^(O;^e2W5Y~I(i%H&SPG<$a$Ofzn%@By_BSNbm@AX1Sn*eAeA-MZOG|3>DKDCZX*;Udq{0-#aH+xYn2?Y7"
    "7GP?vm(QYtK5-*+FsbS$m*TAV^0e4vKMLU^_2aR|D}HCz75<e5v5C}YAum);@T}p5DF)*Qqh*#d4^Yq)F}MPp{_8"
    "6g^Zt0of1DVyMiiNe=El6zZxpx#F+Vh7zi{FQJ{9&$`}M?_JNP-5E>R;7e(W@?=b<x`|{^`W~BQ$7e3Olf(}5aKz"
    ")n~)K^}Xs?+bNvUc-SflI)8EGz9-m0p=~o|F1r9sVSYb3LP&#29`!-r{WGIau^q!|yQ<P=G`KsYG=jmuXFPSfF}}"
    "VqK4C3=axb*u!X8pI;QMJ>xA+vu<gkS|W<mcIwJ0RBI*Wpi-fHDtQXN(1yNL{M;FVuWCV2eZ?2mHF#+ckAD$1IN("
    "Mwy-^sL?dTYm9b>a=#x%;%=5-0EpnJA5dyke&OW<;e8F;NUW?-Ghm~l|3k-nVI-s!hjM;Rh&6p+9=LAD!wRM%6Z>"
    "`bpKD0X3`4i($+!A3Sca}n{H@3$+4_x&km;5Voob}%o!Vm}a`dyVB_&$R@5nlE8h4f>wYSXjre3AGDj&PWb#ec8*"
    "qb*yM8mo>$tLZR#l3!883Nf_*5+B9aUo@)s@S?K!S!M#134R!kCac%$S{{Z(h10V"
)


def _vocabulary() -> list[list[object]]:
    compressed = base64.b85decode("".join(_VOCABULARY_DATA))
    return json.loads(zlib.decompress(compressed))


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def upgrade() -> None:
    for row in _vocabulary():
        unit, expression, phonetic, meaning, page, entry_kind, part_of_speech, confidence = row
        unit_slug = unit.casefold().replace(" ", "-")
        key = f"vocabulary.{_slug(expression)}.full-seed.{unit_slug}"
        payload = {
            "origin": "verified_unit_wordlist_seed",
            "role": "unit_wordlist",
            "lemma": expression.casefold(),
            "entry_kind": entry_kind,
            "part_of_speech": part_of_speech,
            "phonetic": phonetic,
            "definitions_zh": [meaning],
            "examples": [],
            "lesson_printed_page": page,
            "parser_confidence": confidence,
            "requires_review": False,
        }
        op.execute(
            sa.text("""
            INSERT INTO knowledge_points
              (id, source_id, curriculum_node_id, canonical_key, type, title, summary,
               source_page, difficulty, status, content)
            SELECT CAST(:id AS uuid), CAST(:source_id AS uuid), CAST(:node_id AS uuid),
                   :key, 'vocabulary', :title, :summary, :page, 0.2, 'published',
                   CAST(:payload AS jsonb)
            WHERE NOT EXISTS (
                SELECT 1 FROM knowledge_points
                WHERE source_id = CAST(:source_id AS uuid)
                  AND curriculum_node_id = CAST(:node_id AS uuid)
                  AND type = 'vocabulary' AND lower(title) = lower(:title)
            ) ON CONFLICT (canonical_key) DO NOTHING
        """).bindparams(
                id=str(uuid.uuid5(uuid.UUID(SOURCE_ID), key)),
                source_id=SOURCE_ID,
                node_id=NODE_IDS[unit],
                key=key,
                title=expression,
                summary=meaning,
                page=f"P.{page}",
                payload=json.dumps(payload, ensure_ascii=False),
            )
        )
    _refresh_counts()


def _refresh_counts() -> None:
    op.execute(
        sa.text("""
        UPDATE knowledge_sources
        SET knowledge_count = (
                SELECT count(*) FROM knowledge_points
                WHERE source_id = CAST(:source_id AS uuid)
            ), metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object(
                'unit_wordlist_entries', (SELECT count(*) FROM knowledge_points
                    WHERE source_id = CAST(:source_id AS uuid)
                      AND type = 'vocabulary'
                      AND content->>'role' = 'unit_wordlist'))
        WHERE id = CAST(:source_id AS uuid)
    """).bindparams(source_id=SOURCE_ID)
    )


def downgrade() -> None:
    op.execute(
        sa.text("""
        DELETE FROM knowledge_points WHERE source_id = CAST(:source_id AS uuid)
          AND canonical_key LIKE 'vocabulary.%.full-seed.%'
    """).bindparams(source_id=SOURCE_ID)
    )
    _refresh_counts()
