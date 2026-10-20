# Security

## What this software is, in security terms

The control plane is a set of bash hooks and Python scripts that run **inside the operator's own Claude Code
sessions, on the operator's own machine, with the operator's own permissions**. It has no network surface, no
daemon, no third-party dependency except PyYAML. Its security story is therefore not "can an attacker reach it"
but "what does it feed into a model's context, and what does it write to disk".

## Threat model (what the code is reviewed against)

1. **Prompt injection through the dispatch bus.** `hooks/session-start.sh` prints the unacked envelopes for a
   stream into the model's context at every session start. Envelope text is written by *other* sessions and, in
   a multi-contributor repo, by other people. The peek therefore treats it as data: control characters and
   newlines are stripped, fields are capped, malformed envelopes are skipped, and the block is framed with a line
   saying it is data, not instructions. The model still reads it; that is the point. Do not put anything in an
   envelope you would not put in a commit message.
2. **The permission floor is a guardrail, not a boundary.** `config/settings-base.json` and the rules
   `gen-config.py` adds for `protected_paths` are Claude Code `permissions.deny` rules. They match the command
   *text* the model writes; `/bin/rm`, `bash -c '…'` or `git -C . push` bypass any Bash rule, and Anthropic's
   docs say so. The floor stops the model's ordinary mistakes (force-pushing main, deleting the framework); it
   does not stop a hostile prompt. For an OS-level boundary use Claude Code's sandboxing.
3. **Strings that become file names.** Stream ids and envelope ids become ack markers and lease files under
   `.workflow-runtime/` (gitignored). They are validated against `[A-Za-z0-9_-]{1,64}` and the envelope-id shape
   before any write or unlink, so a crafted `--stream ../../x` cannot reach outside the runtime directory.
4. **Loop contracts are code.** `wf loop` runs a contract's `exit_cmd` with `bash -c`, by design: the contract
   author owns the exit oracle. Treat a contract file like a Makefile — review it before running it.
5. **Transcript backups.** `hooks/pre-compact.sh` copies the live session transcript into
   `.claude/transcript-backups/` before compaction. Transcripts can contain anything the session saw, including
   secrets. The directory is gitignored by this repo's `.gitignore`; a host that vendors the framework must keep
   that rule (see `.gitignore`).

## What is not in scope

- Protecting the operator from themselves: every hook and script runs as the operator, in the operator's repo.
- Multi-tenant isolation: one control plane serves one repo and one operator's machine.

## Reporting

Open a GitHub issue for anything that does not disclose an exploitable path; for something you believe is
exploitable, use GitHub's private vulnerability reporting on this repository instead of a public issue. Expect
an answer within two weeks. There is no bug bounty.
