Analyze the current lab assignment and produce a comprehensive Vietnamese summary.

IMPORTANT: The entire output MUST be written in proper Vietnamese with full diacritical marks (dấu tiếng Việt). For example: "Tổng quan" not "Tong quan", "Công việc" not "Cong viec", "Đánh giá" not "Danh gia". This is non-negotiable — every Vietnamese word must have correct diacritics throughout the entire report.

## Step 1: Detect the Lab Directory

Identify the lab directory using these signals (in priority order):
1. If the user provided $ARGUMENTS, use that as the lab path
2. Check which files the user currently has open in their IDE — find the parent lab directory
3. Look for lab directories under the current working directory matching patterns like `Day*`, `day*`, `Lab*`, `lab*`

If multiple labs are found and none is clearly active, ask the user which one to analyze.

## Step 2: Discover Project Structure

List the full directory tree of the lab. Identify and categorize files:

- **Instruction files**: README.md, SCORING.md, EVALUATION.md, INSTRUCTOR_GUIDE.md, exercises.md, worksheets
- **Code skeletons**: Files containing TODO, FIXME, SKELETON markers
- **Report templates**: Files in `report/` or with TEMPLATE in the name
- **Config files**: requirements.txt, package.json, .env.example, Makefile
- **Deliverable examples**: Sample submissions, example reports
- **Test files**: Files in `tests/` or matching test_*.py, *.test.js patterns

## Step 3: Read All Key Files

Read every instruction file, scoring file, evaluation file, report template, and code skeleton found. Also read any deliverable examples — these are gold for understanding expectations.

For code skeletons, search for TODO/FIXME/SKELETON markers and note exact file:line locations.

## Step 4: Produce the Summary Report

Output a structured report in Vietnamese (with full diacritical marks) using the following sections. Use tables and bullet points for clarity. Adapt sections based on what information is actually available — skip sections that don't apply to this lab.

---

### TL;DR — Tóm tắt nhanh

Start with a brief executive summary (5-7 bullet points max) that a student can scan in 30 seconds:
- Tên lab và mục tiêu cốt lõi (1 câu)
- Loại lab: code / product thinking / mixed
- Thời lượng
- Số lượng task chính và task bonus
- Làm cá nhân hay nhóm (tỷ lệ điểm)
- Công thức tính điểm tổng
- Deadline (nếu có)

---

### A. Tổng quan bài Lab
- Tên lab, số thứ tự ngày
- Mục tiêu chính (learning objectives) — what students should understand after completing
- Thời lượng dự kiến (if mentioned)
- Các khái niệm/kỹ năng chính được dạy

### B. Chuẩn bị (Preparation)
- Dependencies cần cài đặt (từ requirements.txt / package.json)
- API keys hoặc config cần thiết (từ .env.example)
- Model / data cần download
- Các bước setup environment

### C. Công việc cần thực hiện

Break down ALL tasks into a clear table:

| # | Công việc | Loại (Cá nhân/Nhóm) | File liên quan | Mô tả chi tiết | Độ ưu tiên |
|---|-----------|---------------------|----------------|-----------------|-------------|

For each task, determine whether it is individual or group work based on:
- Explicit labels in the instructions (INDIVIDUAL, GROUP, etc.)
- Whether it's in an individual report template vs group report template
- Context clues from scoring rubric (individual score vs group score sections)

### D. Các bước thực hiện theo thứ tự (Step-by-step Workflow)

Provide a numbered, chronological workflow combining all tasks. For each step:
- What to do
- Individual or group work
- Estimated portion of total time (if timeline is provided)
- Dependencies on previous steps
- Tips or common pitfalls (from INSTRUCTOR_GUIDE if available)

Additionally, mark **checkpoints** in the workflow — these are natural pause points where the student should verify their progress before continuing. Use a "CHECKPOINT" marker. For example, after implementing core code, there should be a checkpoint to run tests before moving on. Checkpoints help students know they are on track.

Also include a **"Khi thiếu thời gian"** (time-constrained) note at the end of this section: if the student is running out of time, which tasks should be prioritized and which can be skipped with minimal point loss? Rank by points-per-effort ratio.

### E. Code cần implement

For each TODO/SKELETON found:

| File:Line | Function/Method | Yêu cầu | Gợi ý |
|-----------|----------------|----------|--------|

Include parameter types, return types, and any hints from comments or docstrings.

Skip this section entirely if the lab has no code (e.g., product thinking labs).

### F. Metrics đánh giá

List all evaluation criteria mentioned:
- Quantitative metrics (token count, latency, accuracy, cost, etc.)
- Qualitative criteria (code quality, documentation, reflection depth)
- How each metric is measured or collected

### G. Thang điểm chi tiết

Present the full scoring rubric in table format, separated by:
- **Điểm nhóm** (group score): base points + bonus opportunities
- **Điểm cá nhân** (individual score): components and point values
- **Tổng điểm** and calculation formula

If the lab is 100% individual (no group component), state that clearly instead of forcing a group/individual split.

### H. Yêu cầu nộp bài (Submission Requirements)

- Danh sách file cần nộp
- Quy tắc đặt tên file (naming convention)
- Thư mục đặt file
- Format file (md, zip, pdf, etc.)
- Deadline (if mentioned)

### I. Mẹo và lưu ý quan trọng

Extract from INSTRUCTOR_GUIDE, README, or other docs:
- Common mistakes to avoid
- Key insights that help understand the lab better
- Grading philosophy (e.g., "failure analysis is valued as much as working code")
- Any "pro tips" or bonus strategies
