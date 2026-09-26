.PHONY: help install test lint app library backfill enrich features gt probe eval eval-full bench bench-full pool pool-full import-playlists db db-full sqlcheck sqlcheck-full all clean

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
	@echo "  make pool       build a cold-end annotation task to judge by hand"
	@echo "  make pool-full  the same, over the full library"
	@echo "  make sqlcheck   recompute the sample's reported numbers in SQLite"
	@echo "  make sqlcheck-full  the same for the committed reports and README"
	@echo ""
	@echo "  Full pipeline (needs LASTFM_API_KEY; see .env.example):"
	@echo "  make library    1. pull tracks + sub-genre tags from Last.fm"
	@echo "  make backfill   2. fill tags the first pass missed"
	@echo "  make enrich     3. add listeners / playcount / year"
	@echo "  make features   4. add ReccoBeats audio features"
	@echo "  make import-playlists  add your Spotify playlists (needs SPOTIFY_CLIENT_ID + _PLAYLIST_IDS)"
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

# Adds the owner's own Spotify playlists to the library, tagged
# source=spotify_playlist. Run before backfill / enrich / features / gt, which
# then fill in only the new tracks.
import-playlists:
	$(PY) scripts/import_playlists.py --songs $(SONGS)

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

# The pool of candidates to judge by hand, sampled from the two quintiles the
# Last.fm labels cannot reach. Writes the task, a provenance key used only when
# scoring, and a markdown worksheet.
pool:
	$(PY) scripts/build_pool.py
	@echo
	@echo "Sample worksheet -> reports/sample/annotation_pool.md"

pool-full:
	$(PY) scripts/build_pool.py \
		--songs $(SONGS) --ground-truth data/ground_truth.json \
		--out data/annotation_pool.json --key data/annotation_pool_key.json \
		--sheet reports/annotation_pool.md

# SQLite, derived from the JSON: the library, labels and benchmark rankings,
# with every derived quantity defined as SQL (sql/schema.sql). Gitignored.
db:
	$(PY) scripts/build_db.py

db-full:
	$(PY) scripts/build_db.py \
		--songs $(SONGS) --ground-truth data/ground_truth.json --out data/kpoprec.db

# Recompute every published number in SQL and diff it against the report that
# printed it. Fails on any mismatch. The sample variant regenerates the sample
# reports first, since they are gitignored and may be stale or absent.
sqlcheck: eval bench db
	$(PY) scripts/sql_crosscheck.py

sqlcheck-full: db-full
	$(PY) scripts/sql_crosscheck.py \
		--db data/kpoprec.db --reports reports --readme README.md

# The committed benchmark, over the full library and ground truth.
bench-full:
	$(PY) scripts/evaluate.py \
		--songs $(SONGS) --ground-truth data/ground_truth.json \
		--outdir reports --figdir figures

all: library backfill enrich features gt eval bench

clean:
	rm -rf .pytest_cache __pycache__ src/**/__pycache__ tests/__pycache__
	find . -name '*.pyc' -delete
