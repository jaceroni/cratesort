# CrateSort — Phase 2 Audit & CLAUDE.md Update

## What to do

Before we start Phase 3 (Serato Integration), do a full audit of everything 
built so far. Review the codebase, update CLAUDE.md, and flag anything that 
needs attention.

## Step 1: Codebase audit

Read through every implemented module and check for:

1. **Consistency** — Do all modules use the same patterns? Same import style, 
   same dataclass conventions, same error handling approach? If one module does 
   something differently, flag it.

2. **Integration** — Do the modules actually work together as a pipeline? Run 
   the full chain: scanner → classifier → filename cleaner → "The" handler → 
   metadata fixer → artist consolidator → duplicate detector. Does data flow 
   cleanly from one to the next? Are there type mismatches, missing fields, or 
   assumptions that don't hold?

3. **Edge cases** — Review error handling across all modules. What happens with:
   - Empty directories
   - Files with zero metadata
   - Files with corrupted/unreadable tags
   - Extremely long filenames or paths
   - Unicode and special characters in artist names, titles, paths
   - Very large directories (performance considerations)

4. **Dead code / stubs** — Are there any leftover stubs that should have been 
   implemented but weren't? Any TODO comments that need to be addressed now 
   vs later?

5. **Test coverage** — Review the test runners. Are they testing the right 
   things? Any obvious scenarios missing?

6. **Cross-platform** — Check path handling across all modules. Are we using 
   pathlib consistently? Any hardcoded `/` separators that would break on 
   Windows? Any case-sensitivity assumptions?

7. **The mapping table** — Is the style-to-genre mapping baked into 
   classifier.py cleanly? Is it easy to add/remove entries? Does it match the 
   project plan's taxonomy exactly?

8. **Module boundaries** — Is any module doing work that belongs in a different 
   module? Is there duplicated logic that should be in a shared utility?

## Step 2: Run the full pipeline

Run scanner → classifier → all Phase 2 modules against the test library at:
```
/Users/jacebrown/Desktop/cratesort-test-library
```

Verify everything still works end-to-end. Report any failures or unexpected 
results.

## Step 3: Update CLAUDE.md

Update the project's CLAUDE.md to reflect the current state of the codebase. 
It should include:

- **What's implemented** — Every module, what it does, what it returns
- **What's NOT implemented yet** — Stubs, future modules, planned features
- **Data flow** — How the modules connect: scanner output → classifier input, etc.
- **Key decisions made during development** — Any deviations from the original 
  plan, architectural choices, library selections
- **The style-to-genre mapping** — Where it lives, how to modify it
- **Test library location and structure** — For future sessions
- **Normalization utilities** — What's in src/utils/normalize.py and who uses it
- **Important rules** — Serato metadata is never touched, comments are sacred, 
  all modules are proposal engines (no writes), cross-platform path handling
- **Known issues or limitations** — Anything flagged during the audit
- **Next up** — Phase 3 (Serato Integration) is the next build target

Keep CLAUDE.md concise but complete — it's the reference document for every 
future Claude Code session. A new session should be able to read CLAUDE.md and 
understand the full state of the project without reading every source file.

## Step 4: Report

Give me a summary of:
- Everything checked and confirmed good
- Anything that needed fixing (and what you fixed)
- Anything that needs my input or a decision
- The updated state of the project
