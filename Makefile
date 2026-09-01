.PHONY: help install test lint app library backfill enrich features gt probe eval eval-full bench bench-full all clean

PY := python3
SONGS ?= data/songs.json

help:
	@echo "K-pop cold-start recommender"
	@echo ""
	@echo "  make install    install dependencies"
	@echo "  make test       run the test suite"
	@echo "  make app        serve the web app on http://127.0.0.1:5000"
	@echo ""
	@echo "  make eval       run the analysis on the bundled sample"
	@echo "                  (no API key needed — start here)"
	@echo "  make bench      rank-quality benchmark on the bundled sample"
	@echo "  make eval-full  regenerate the committed reports from the full library"
	@echo "  make bench-full regenerate the committed benchmark from the full library"
	@echo ""
	@echo "  Full pipeline (needs LASTFM_API_KEY; see .env.example):"
	@echo "  make library    1. pull tracks + sub-genre tags from Last.fm"
	@echo "  make backfill   2. fill tags the first pass missed"
	@echo "  make enrich     3. add listeners / playcount / year"
	@echo "  make features   4. add ReccoBeats audio features"
	@echo "  make probe      -  check ground-truth density before committing to it"
	@echo "  make gt         5. build pseudo ground truth + diagnostics"
	@echo "  make all        run 1-5 end to end (~40 min, rate-limited)"

install:
	$(PY) -m pip install -r requirements.txt

test:
	$(PY) -m pytest tests/ -q

app:
	$(PY) app/server.py

# ── Pipeline ────────────────────────────────────────────────────────────────

library:
	$(PY) scripts/build_library.py --out $(SONGS)

backfill:
	$(PY) scripts/backfill_tags.py --songs $(SONGS)

enrich:
	$(PY) scripts/enrich_metadata.py --songs $(SONGS)

features:
	$(PY) scripts/build_features.py --songs $(SONGS)

probe:
	$(PY) scripts/check_gt_density.py --songs $(SONGS)

gt:
	$(PY) scripts/build_ground_truth.py --songs $(SONGS)

# Runs the analysis against the bundled sample, so a fresh clone produces real
# output with no API key. Writes to reports/sample/ and figures/sample/ (both
# gitignored) so a demo run never rewrites the committed full-corpus results.
eval:
	$(PY) scripts/analyze_tag_sparsity.py \
		--songs data/songs.sample.json \
		--outdir reports/sample --figdir figures/sample
	@echo
	@echo "Sample results -> reports/sample/tag_sparsity_summary.md"
	@echo "Committed full-corpus results are in reports/ (1,267 tracks)."

# Regenerates the committed reports and figures from the full library.
# Requires data/songs.json, i.e. a completed pipeline run.
eval-full:
	$(PY) scripts/analyze_tag_sparsity.py --songs $(SONGS)

# Ranking benchmark on the bundled sample: five policies scored against the
# sample ground truth. No API key needed.
bench:
	$(PY) scripts/evaluate.py
	@echo
	@echo "Sample results -> reports/sample/eval_summary.md"
	@echo "Committed full-corpus results are in reports/eval_summary.md."

# The committed benchmark, over the full library and ground truth.
bench-full:
	$(PY) scripts/evaluate.py \
		--songs $(SONGS) --ground-truth data/ground_truth.json \
		--outdir reports --figdir figures

all: library backfill enrich features gt eval bench

clean:
	rm -rf .pytest_cache __pycache__ src/**/__pycache__ tests/__pycache__
	find . -name '*.pyc' -delete
