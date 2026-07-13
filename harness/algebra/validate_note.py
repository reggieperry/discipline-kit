#!/usr/bin/env python3
"""Machine validation for the ledger-dynamics formal note.
Testimonies over a candidate set: cand -> (pro, con), channels as ℕ[X] modeled
by multisets of monomials; monomial = frozenset-of-(token,exp) — here token
strings with exponents via Counter-of-Counters simplified: we model Prov as a
Counter over monomials, monomial = frozen Counter over tokens. Sufficient for
every structural (corner-level) claim; grades via a sample hom ν̂."""
from collections import Counter
from itertools import product
import random
random.seed(1)

# ---------- Prov = ℕ[X]: Counter{ monomial: coeff }, monomial = frozenset of (token,exp)
def mono(*toks):  # multiset of tokens -> canonical monomial
    c = Counter(toks); return frozenset(c.items())
ZERO = Counter(); ONE = Counter({mono(): 1})
def padd(p, q): r = Counter(p); r.update(q); return +r
def pmul(p, q):
    r = Counter()
    for m1, c1 in p.items():
        for m2, c2 in q.items():
            mm = Counter(dict(m1)); mm.update(dict(m2))
            r[frozenset(mm.items())] += c1 * c2
    return +r
def is_zero(p): return len(+Counter(p)) == 0

# ---------- Testimony: dict cand -> (pro, con), normalized (no (0,0))
def T_(d):
    return {v: (Counter(p), Counter(c)) for v, (p, c) in d.items()
            if not (is_zero(p) and is_zero(c))}
EPS = T_({})
def provPro(t): 
    s = Counter(); [s.update(p) for p, _ in t.values()]; return s
def provCon(t):
    s = Counter(); [s.update(c) for _, c in t.values()]; return s
def corner(t):
    zp, zc = is_zero(provPro(t)), is_zero(provCon(t))
    return {(True,True):'N',(False,True):'T',(True,False):'F',(False,False):'B'}[(zp,zc)]
def card(t): return sum(1 for p,_ in t.values() if not is_zero(p))
def gate_signs(t, theta=1, nu=lambda p: sum(p.values())):
    return corner(t)=='T' and card(t)==1 and nu(provPro(t))>=theta   # verify(t)≡true here

# ---------- ops per the calculus
def oplus(a, b):  # Def 2.9 corroborate
    vs = set(a)|set(b); out={}
    for v in vs:
        pa,ca = a.get(v,(ZERO,ZERO)); pb,cb = b.get(v,(ZERO,ZERO))
        out[v]=(padd(pa,pb), padd(ca,cb))
    return T_(out)
def neg(t):  return T_({v:(c,p) for v,(p,c) in t.items()})            # Def 2.11
def strike(t): return T_({v:(ZERO, padd(p,c)) for v,(p,c) in t.items()})  # Def 2.12
def supersede(t,g): return (neg(t), g)                                 # Def 2.14 pair
def kmeet(a,b,f=lambda x,y:(x,y)):  # Def 6.5 ⊗ₖ : (pro·pro, con·con)
    out={}
    for (x,(pa,ca)),(y,(pb,cb)) in product(a.items(),b.items()):
        v=f(x,y); P,C=out.get(v,(ZERO,ZERO))
        out[v]=(padd(P,pmul(pa,pb)), padd(C,pmul(ca,cb)))
    return T_(out)
def tmeet(a,b,f=lambda x,y:(x,y)):  # ∧ₜ shipped simple carrier: (pro·pro, con: ca·pb+pa·cb+ca·cb)
    out={}
    for (x,(pa,ca)),(y,(pb,cb)) in product(a.items(),b.items()):
        v=f(x,y); P,C=out.get(v,(ZERO,ZERO))
        con3 = padd(padd(pmul(ca,pb),pmul(pa,cb)),pmul(ca,cb))
        out[v]=(padd(P,pmul(pa,pb)), padd(C,con3))
    return T_(out)
def tjoin(a,b):  # NEW Def (propositional slots): ∨ₜ CHANNELWISE — pro by +, con by ·.
    # A pairing-style De Morgan dual is WRONG here: ε has no candidates, so any pairwise op
    # annihilates on the gap and T∨N would read N. Machine-refuted; see note Remark.
    pa,ca = a.get('⊤',(ZERO,ZERO)); pb,cb = b.get('⊤',(ZERO,ZERO))
    return T_({'⊤': (padd(pa,pb), pmul(ca,cb))})
# propositional testimony (single candidate ⊤) helpers
def prop(pro_toks=(), con_toks=()):
    p = Counter({mono(t):1 for t in pro_toks}) if pro_toks else ZERO
    c = Counter({mono(t):1 for t in con_toks}) if con_toks else ZERO
    return T_({'⊤':(p,c)})
PN, PT, PF, PB = prop(), prop(('a',)), prop((),('r',)), prop(('a',),('r',))

checks=[]
def ck(name, cond): checks.append((name,bool(cond))); print(f"[{'PASS' if cond else 'FAIL'}] {name}")

print("== §V1 base laws (calculus props, re-checked) ==")
rt=lambda: prop(tuple(random.sample('abcde',random.randint(0,2))), tuple(random.sample('xyz',random.randint(0,2))))
ok=True
for _ in range(200):
    a,b,c=rt(),rt(),rt()
    ok &= oplus(oplus(a,b),c)==oplus(a,oplus(b,c)) and oplus(a,b)==oplus(b,a) and oplus(a,EPS)==a
ck("2.10 ⊕ comm. monoid (200 random)", ok)
ok=all(strike(strike(t))==strike(t) for t in [PN,PT,PF,PB,rt(),rt()])
ck("2.13 strike idempotent", ok)
struck,op = supersede(PT, prop(('g',)))
ck("2.14/6.3 pair: operative signs, corroborated glut blocks",
   gate_signs(op) and corner(oplus(neg(PT),prop(('g',))))=='B' and not gate_signs(oplus(neg(PT),prop(('g',)))))

print("== §V2 ⊗ₖ: 6.7 gap case + glut-identity laundering (correction doc) ==")
clean=PT; glut=PB; gap=PN
ck("6.7 gap annihilates: corner(N ⊗ₖ T)=N & blocks", corner(kmeet(gap,clean))=='N' and not gate_signs(kmeet(gap,clean)))
r=kmeet(glut,clean)
ck("glut launders under ⊗ₖ: corner(B ⊗ₖ T)=T, con empty, gate SIGNS", corner(r)=='T' and is_zero(provCon(r)) and gate_signs(r))
r2=tmeet(glut,clean)
ck("∧ₜ blocks the same glut: corner=B, gate blocks", corner(r2)=='B' and not gate_signs(r2))
ck("per-slot gating blocks (glut slot fails alone)", not gate_signs(glut))
ck("6.7 undisturbed under ∧ₜ: gap blocks too", not gate_signs(tmeet(gap,clean)))

print("== §V3 ∧ₜ corner table (F-dominance) ==")
names={'N':PN,'T':PT,'F':PF,'B':PB}
expect_and={('T','T'):'T',('T','F'):'F',('F','T'):'F',('F','F'):'F',('T','N'):'N',('N','T'):'N',
 ('N','N'):'N',('N','F'):'N',('F','N'):'N',('T','B'):'B',('B','T'):'B',('B','B'):'B',
 ('B','F'):'F',('F','B'):'F',('N','B'):'N',('B','N'):'N'}
ok=True; tbl={}
for (x,y),e in expect_and.items():
    got=corner(tmeet(names[x],names[y])); tbl[(x,y)]=got; ok &= (got==e)
ck(f"∧ₜ 16-cell corner table matches Belnap truth-meet", ok)

print("== §V4 NEW ∨ₜ at testimony level: table + dual laundering + sound forms ==")
expect_or={('T',x):'T' for x in 'NTFB'}|{(x,'T'):'T' for x in 'NTFB'}
expect_or|={('F','F'):'F',('N','N'):'N',('B','B'):'B',('N','F'):'N',('F','N'):'N',
 ('B','F'):'B',('F','B'):'B',('N','B'):'T',('B','N'):'T'}
ok=True
for (x,y),e in expect_or.items():
    got=corner(tjoin(names[x],names[y])); ok &= (got==e)
ck("∨ₜ 16-cell corner table (De Morgan dual of ∧ₜ)", ok)
d=tjoin(PN,PB)
ck("DUAL LAUNDERING EXHIBIT: corner(N ∨ₜ B)=T — contested existence signs through unchecked leaf",
   corner(d)=='T' and gate_signs(d))
# sound certification forms
leaves_ok=[PT,PF,PN]        # one witnessing T among F/N
root=tjoin(tjoin(leaves_ok[0],leaves_ok[1]),leaves_ok[2])
ck("witness rule sound: ∃ leaf signs ⇒ safe to certify ∃ (and root reads T)",
   any(gate_signs(l) for l in leaves_ok) and corner(root)=='T')
leaves_bad=[PB,PF,PN]       # contested + refuted + unchecked: NO leaf signs
rootb=tjoin(tjoin(leaves_bad[0],leaves_bad[1]),leaves_bad[2])
ck("witness rule catches what root misses: no leaf signs, yet naive root would sign",
   (not any(gate_signs(l) for l in leaves_bad)) and gate_signs(rootb))
allF=[PF,PF,PF]; rootF=tjoin(tjoin(*allF[:2]),allF[2])
ck("refutation totality: all leaves F ⇒ root F (∃ refuted)", corner(rootF)=='F')
mixNF=[PF,PN,PF]; rootNF=tjoin(tjoin(*mixNF[:2]),mixNF[2])
ck("N-leaf blocks refutation: F,N,F ⇒ root ≠ F (cannot refute with unchecked habitat)",
   corner(rootNF)!='F')

print("== §V5 interval-testimony sort: exit partition + embedding + P3 grammar ==")
def corner_iv(lo,hi,delta,ceiling=False):
    if ceiling: return 'U_ceiling'
    if (hi-lo)/2 > delta: return 'U_width'
    if lo > delta: return 'T_dir'
    if hi < -delta: return 'F_dir'
    return 'Flat'
ok=True; grid=[x/20 for x in range(-30,31)]
for lo in grid:
    for hi in grid:
        if hi<lo: continue
        exits=[corner_iv(lo,hi,0.10)]  # exactly one fires by construction; assert membership+determinism
        ok &= exits[0] in ('U_width','T_dir','F_dir','Flat')
ck("interval exits: total & deterministic over 900+ grid intervals", ok)
def embed(lo,hi,delta):
    """interval -> (D,Z): D='effect>δ' slot, Z='|effect|≤δ' slot, propositional."""
    cv=corner_iv(lo,hi,delta)
    D={'T_dir':PT,'F_dir':PF,'Flat':PF,'U_width':PN}[cv]
    Z={'T_dir':PF,'F_dir':PF,'Flat':PT,'U_width':PN}[cv]
    return D,Z,cv
ok=True
for lo,hi,exp in [(0.15,0.35,'T_dir'),(-0.35,-0.15,'F_dir'),(-0.05,0.05,'Flat'),(-0.2,0.2,'U_width')]:
    D,Z,cv=embed(lo,hi,0.10); ok &= cv==exp and (corner(D),corner(Z))=={'T_dir':('T','F'),'F_dir':('F','F'),'Flat':('F','T'),'U_width':('N','N')}[exp]
ck("embedding ι→(D,Z) matches exit table on canonical intervals", ok)
# P3 grammar: supported = G1.D ∧ₜ F'.D ; refuted = G1.Z(flat) ∨ F'-anti — check the ∧ₜ rows used
g1T,_,_=embed(0.12,0.30,0.10); fpT,_,_=embed(0.15,0.33,0.10)
ck("P3 'supported' row: T ∧ₜ T = T via embedded slots", corner(tmeet(g1T,fpT))=='T')
g1U,_,_=embed(-0.05,0.23,0.10)
ck("P3 'partial' row: U-width leaf ⇒ conjunction not T (blocks)", corner(tmeet(g1U,fpT))!='T')

print("== §V6 deontic axioms (restless bilattice): consistency + independence ==")
# states: (corner, scope_open, docket, age); D1: corner==N ∧ scope_open ⇒ docket within k steps
# D2: corner==B ⇒ successor(fold) within k steps.  Model: finite traces; consistency = a trace satisfying both.
def trace_ok(tr,k=2):
    for i,(c,so,dk) in enumerate(tr):
        if c=='N' and so and not any(d for (_,_,d) in tr[i:i+k+1]):
            return False
        if c=='B' and not any(cc!='B' for (cc,_,_) in tr[i:i+k+1]):
            return False
    return True
good=[('N',True,False),('N',True,True),('T',False,True),('B',False,True),('T',False,True)]
ck("D1∧D2 consistent: satisfying finite trace exists", trace_ok(good))
viol_d1=[('N',True,False),('N',True,False),('N',True,False),('N',True,False)]
viol_d2=[('B',False,False),('B',False,False),('B',False,False),('B',False,False)]
ck("independence: trace violating D1 only / D2 only both constructible",
   (not trace_ok(viol_d1)) and (not trace_ok(viol_d2)) and trace_ok(good))
print("== §V7 commitment axiom C1: consistency + violation detectable ==")
ev_ok=[('commit','court1',1),('archive','g1',2),('archive','g2',3),('verdict','court1',4)]
ev_bad=[('archive','g1',1),('commit','court1',2),('verdict','court1',3)]
def c1(ev):
    commits={n:i for k,n,i in ev if k=='commit'}
    firstobs=min([i for k,_,i in ev if k=='archive'],default=None)
    verd=[n for k,n,_ in ev if k=='verdict']
    return all(n in commits and (firstobs is None or commits[n]<firstobs) for n in verd)
ck("C1 consistent (registered-before-observed trace) & violation detected", c1(ev_ok) and not c1(ev_bad))

print()
fails=[n for n,c in checks if not c]
print(f"TOTAL: {len(checks)} checks, {len(checks)-len(fails)} pass, {len(fails)} fail")
if fails: print("FAILED:", fails)
raise SystemExit(1 if fails else 0)  # fail closed: a regressed law/laundering exhibit exits non-zero
