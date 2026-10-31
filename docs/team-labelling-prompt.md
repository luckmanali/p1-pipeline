# Player 1 — reusable AI labelling prompt

31 October 2026. Send this file with the [reviewer guide](cvat-reviewer-guide.md) and [Frame 2 plan](frame-two-labelling-plan.md). Fill in the assignment below; credentials belong in the authorised connection, not in the prompt. The coordinator supplies the source-frame mapping and match-area boundary.

Manual reviewers only need their own CVAT account. This prompt is for an image-capable AI assistant supporting them. It cannot connect an ordinary chatbot to CVAT or install an unattended annotation service. Drafts can instead be prepared centrally and handed to each reviewer.

Copy the following:

```text
Help me prepare and review Player 1 football annotations in CVAT.

Assignment:
- CVAT URL and task/job: [coordinator supplies]
- Match ID, pitch/camera and frame range: [coordinator supplies]
- Split: [training / validation / test; do not choose or change this]
- Source frames, timestamp manifest and approved match-area boundary: [location]
- Human reviewer: [name]
- Annotation guide: [attach the Player 1 reviewer guide and Frame 2 plan]

Read the supplied guide and any applicable repository AGENTS.md. Verify
the assigned task, labels, source-frame mapping and existing saved work.
If access, assignment, split or the match boundary is missing, explain
what is missing before editing. Never invent access or claim unseen work.

Prepare AI drafts only for this assigned job while no human is editing it.
Use player for every visible person inside the agreed main-match area,
including keepers and any referees/substitutes/spectators inside it.
Use football for every visible sports ball there, including spare balls.
Exclude other pitches; do not force the person count to equal team size.
Use the guide's person bottom-centre and ball-centre scope rules.
Do not add team/identity/goal classes or change the shared label schema.

Draw tight rectangles around visible extent, clipped at image borders.
Keep the full box for an in-scope object. Inspect original-resolution
pixels and nearby video frames for difficult cases. Never invent a box
for a fully hidden/off-screen ball or an imagined hidden body. Preserve
person boxes when the ball is absent. Flag ambiguous objects with a CVAT
issue containing the source timestamp, region and a specific question.

For training jobs, use only the coordinator-approved proposal model or
visual drafting workflow and record its provenance. For validation/test,
draft independently of the model being evaluated; do not use its outputs
to choose frames, labels or acceptance. Do not train or tune on these jobs.

Preserve human corrections and unrelated annotations. Use targeted
official CVAT API/SDK updates with before/after read-back checks; our
community MCP is read-only. Do not clear/import over existing labels,
duplicate a completed draft, move data to another host or expose tokens.

Then hand the job to the human. Explain how to inspect EVERY assigned
frame, search for missing balls/people, fix boxes, remove false labels
and save. No issues or high AI confidence does not mean reviewed.
Ask for actual reviewed ranges and unresolved questions; do not infer
approval. Leave acceptance to the coordinator after the required second
review and adjudication. Do not resolve unanswered questions yourself.

Finish with a short handover: task/job, drafted and human-reviewed ranges
(separately), changes, open issues, exclusions proposed for adjudication,
and saved-state verification. Do not claim full-video coverage, identities
or goal decisions from these sampled detector images.
```

After reviewing, a human can send the coordinator:

```text
Job: [URL]
Reviewer: [name]
Frames actually checked: [ranges]
Corrections saved: [yes/no]
Outstanding issues: [IDs and short notes, or none]
Second review/adjudication: [person and scope, or pending]
Ready for coordinator acceptance: [yes/no]
```
