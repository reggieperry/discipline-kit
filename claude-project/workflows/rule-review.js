export const meta = {
  name: 'rule-review',
  description: "Review a diff against the repo's own discipline rules, targeted by enforcement grade",
  whenToUse:
    'Reviewing a change against the rules this repo actually declares, rather than against general ' +
    'good practice. Pass args from `python3 scripts/rules-manifest.py` and `git diff --name-only`.',
  phases: [
    { title: 'Unenforced', detail: 'one agent per review-and-convention rule — the only instrument these have' },
    { title: 'Residue', detail: 'the non-mechanical half of the partly-mechanical rules' },
    { title: 'Report', detail: 'findings, plus what was deliberately not reviewed' },
  ],
}

// ---------------------------------------------------------------------------
// args: { base: string, files: string[], rules: [{name, file, paths, grade}] }
//
// The main loop gathers both, because a workflow script has no filesystem: `git diff --name-only`
// for the files and `scripts/rules-manifest.py` for the rules. What the script contributes is the
// part that should be deterministic — matching one against the other, and deciding where review
// attention goes.
// ---------------------------------------------------------------------------

if (!args || !args.files || !args.rules) {
  throw new Error(
    'rule-review needs {base, files, rules}. Gather with:\n' +
      "  git diff --name-only <base>...HEAD\n" +
      '  python3 scripts/rules-manifest.py'
  )
}

/** A `paths:` glob as a regex. Handles the three forms the rules actually use. */
function globToRe(glob) {
  // A tokenizer rather than chained replaces: the chained form needs placeholder characters to
  // hold `**` between passes, and any character chosen for that is either legal in a glob or
  // invisible in a diff.
  let out = ''
  for (let i = 0; i < glob.length; ) {
    if (glob.startsWith('**/', i)) {
      out += '(?:.*/)?' // any number of leading segments, including none
      i += 3
    } else if (glob.startsWith('**', i)) {
      out += '.*'
      i += 2
    } else if (glob[i] === '*') {
      out += '[^/]*' // one segment only
      i += 1
    } else {
      out += glob[i].replace(/[.+^${}()|[\]\\?]/, '\\$&')
      i += 1
    }
  }
  return new RegExp('^' + out + '$')
}

function applies(rule, files) {
  const res = rule.paths.map(globToRe)
  return files.filter((f) => res.some((re) => re.test(f)))
}

const matched = args.rules
  .map((r) => ({ ...r, hits: applies(r, args.files) }))
  .filter((r) => r.hits.length > 0)

const unenforced = matched.filter((r) => r.grade === 'review and convention')
const partial = matched.filter((r) => r.grade === 'partly mechanical')
const mechanical = matched.filter((r) => r.grade === 'mechanically enforced')

log(
  `${args.files.length} changed file(s) · ${matched.length} of ${args.rules.length} rules apply · ` +
    `${unenforced.length} unenforced, ${partial.length} partial, ${mechanical.length} mechanical (skipped)`
)

if (matched.length === 0) {
  return {
    reviewed: [],
    skipped: [],
    note:
      'NOTHING WAS REVIEWED. No rule\'s paths glob matched any changed file, which is not the same ' +
      'as a clean review — check whether the file list or the globs are wrong before reading this ' +
      'as a pass.',
  }
}

const FRAME = `
You are reviewing a change against ONE rule this repository declares for itself. Not general good
practice — this rule, as written, in this repo.

READ THE RULE FILE FIRST, in full. Then read the change. Both are on disk and you have the tools.

  base ref:      ${args.base || 'main'}
  changed files: see the per-rule list below (only files this rule's paths glob matches)

Get the diff with: git diff ${args.base || 'main'}...HEAD -- <the files listed>

REPORT ONLY WHAT THE RULE SAYS. If the rule does not cover something you dislike, that is not a
finding under this rule — say so and leave it. If the change is clean against this rule, say that
plainly; inventing a finding to look useful is worse than reporting none.

Every finding needs file:line, the rule's own words for what is violated, and a concrete fix. A
finding you cannot anchor to a line and to a sentence of the rule is not a finding yet.
`

const SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['rule', 'filesExamined', 'findings', 'clean'],
  properties: {
    rule: { type: 'string' },
    filesExamined: { type: 'integer', description: 'How many files you actually read the diff for' },
    clean: { type: 'boolean', description: 'true when the change violates nothing in this rule' },
    findings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['file', 'line', 'rulePhrase', 'problem', 'fix'],
        properties: {
          file: { type: 'string' },
          line: { type: 'integer' },
          rulePhrase: { type: 'string', description: "The rule's own words that this violates" },
          problem: { type: 'string' },
          fix: { type: 'string' },
        },
      },
    },
  },
}

phase('Unenforced')

// These rules have no check behind them. A reader is the only instrument they will ever get, which
// is the whole argument for spending a separate agent on each rather than one agent on all of them.
const unenforcedFindings = await parallel(
  unenforced.map((r) => () =>
    agent(
      `${FRAME}\n\nRULE: ${r.name}  (${r.file})\nENFORCEMENT: review and convention — NOTHING MECHANICAL CHECKS THIS. ` +
        `If you do not catch it here, nothing does.\n\nFILES THIS RULE COVERS:\n${r.hits.map((h) => '  ' + h).join('\n')}`,
      { label: `rule:${r.name}`, phase: 'Unenforced', schema: SCHEMA }
    )
  )
)

phase('Residue')

// Partly-mechanical rules: the build already refuses part of what these say. Re-deriving that part
// spends attention on something with an owner, so the agent is pointed at the remainder.
const partialFindings = await parallel(
  partial.map((r) => () =>
    agent(
      `${FRAME}\n\nRULE: ${r.name}  (${r.file})\nENFORCEMENT: partly mechanical.\n\n` +
        `THE RULE'S OWN GRADE PARAGRAPH SAYS WHICH PART IS ENFORCED — read it first and review ONLY ` +
        `THE REMAINDER. A finding the compiler or the gate already refuses is not worth reporting: it ` +
        `cannot reach main, and reporting it spends the reader's attention on something that has an ` +
        `owner. Say explicitly which part you treated as already covered.\n\n` +
        `FILES THIS RULE COVERS:\n${r.hits.map((h) => '  ' + h).join('\n')}`,
      { label: `rule:${r.name}`, phase: 'Residue', schema: SCHEMA }
    )
  )
)

phase('Report')

const all = [...unenforcedFindings, ...partialFindings].filter(Boolean)
const findings = all.flatMap((r) => (r.findings || []).map((f) => ({ ...f, rule: r.rule })))
const silent = all.filter((r) => r.filesExamined === 0).map((r) => r.rule)

return {
  findings,
  reviewed: all.map((r) => ({ rule: r.rule, files: r.filesExamined, clean: r.clean })),
  skippedAsMechanical: mechanical.map((r) => ({
    rule: r.name,
    files: r.hits.length,
    why: 'the build refuses this; a reviewer re-checking it duplicates an owner',
  })),
  examinedNothing: silent,
  denominator: {
    changedFiles: args.files.length,
    rulesDeclared: args.rules.length,
    rulesApplicable: matched.length,
    rulesReviewed: all.length,
  },
  // The last two fields are the ones that stop a clean result reading as a thorough one. A rule that
  // examined no files, and a rule skipped as mechanical, are both absences — and an absence nobody
  // prints is indistinguishable from a check that passed.
}
