"""The SQL layer is only worth having if it agrees with the Python it shadows,
exactly, on the same inputs -- a cross-check that is merely close cannot tell a
rounding difference from a bug. Each test here pins one definition in
sql/schema.sql or sql/checks/ to the Python that the published numbers came
from, at full precision, on the bundled sample."""

import importlib.util
import json
import subprocess
import sys

import numpy as np
import pytest

from kpoprec import config, db
from kpoprec.metrics import METRIC_NAMES
from kpoprec.pooling import evaluable_seeds
from kpoprec.recommend import POLICIES, Library, can_serve, quintile_of

from test_recommend import song

ROOT = config.ROOT
EXACT = 1e-12
REPEATS = 2  # random draws; enough to exercise the per-draw averaging


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def sample():
    songs = json.loads(config.SONGS_SAMPLE_JSON.read_text(encoding="utf-8"))
    gt = json.loads((config.DATA_DIR / "ground_truth.sample.json").read_text(encoding="utf-8"))
    conn = db.connect()
    db.build(conn, songs, gt, repeats=REPEATS)
    return songs, gt, conn


def tiny(songs, gt=None, **kw):
    conn = db.connect()
    db.build(conn, [dict(s, dur=200) for s in songs], gt or {}, **kw)
    return conn


# ── Storage ─────────────────────────────────────────────────────────────────

def test_the_json_survives_a_round_trip(sample):
    """The database claims to hold what songs.json holds. Rebuilding the JSON
    from the tables is the only way to know nothing was dropped or coerced."""
    songs, _, conn = sample
    assert db.export_songs(conn) == songs


def test_an_unknown_field_stops_the_load():
    """A new pipeline field must be added to the schema on purpose -- the
    playlist import added `source` and `year_spotify` that way. Silently
    dropping one would make the database disagree with the JSON while claiming
    to mirror it."""
    with pytest.raises(ValueError, match="explicit"):
        tiny([dict(song("a"), explicit=True)])


def test_the_playlist_fields_survive_a_round_trip():
    """`source` and `year_spotify` are on the record only for imported tracks,
    and absent means the Last.fm pull. Neither may be invented on the way out."""
    songs = [
        dict(song("old"), listeners=10),
        dict(song("new"), source="spotify_playlist", year_spotify=2022, spotify_id="x" * 22),
    ]
    songs = [dict(s, dur=200, durStr="3:20") for s in songs]
    songs = [{k: v for k, v in s.items() if k != "features"} for s in songs]
    conn = db.connect()
    db.build(conn, songs, {}, repeats=1)
    assert db.export_songs(conn) == songs
    got = {r["track_id"]: r["source"] for r in conn.execute("SELECT * FROM track_source")}
    assert got == {0: "lastfm_tag", 1: "spotify_playlist"}


# ── Definitions ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("n", [7, 12, 13, 1267])
def test_quintiles_are_the_benchmarks_not_ntile(n):
    """The view reproduces recommend.quintile_of, ties and all. NTILE(5) would
    not: it gives the spare tracks to the first groups, and at n = 1,267 one
    track lands in a different quintile."""
    rng = np.random.default_rng(n)
    listeners = rng.integers(0, max(n // 3, 2), n)  # plenty of ties
    conn = tiny([song(f"t{i}", listeners=int(v)) for i, v in enumerate(listeners)])
    got = [q for _, q in conn.execute("SELECT track_id, quintile FROM track_quintile ORDER BY track_id")]
    assert got == list(quintile_of(listeners.astype(float)))


def test_a_track_with_no_listener_count_has_no_stratum_in_sql_either():
    """Same rule as recommend.quintile_of: unknown popularity is not zero. The
    view gives such a track no row, and the known tracks are cut as if it were
    not there."""
    known = [song(f"k{i}", listeners=i + 1) for i in range(20)]
    conn = tiny(known[:10] + [dict(song("u"), listeners=None)] + known[10:])
    rows = {r["track_id"]: r["quintile"] for r in conn.execute("SELECT * FROM track_quintile")}
    assert 10 not in rows
    lib = Library(known)
    assert [rows[i] for i in sorted(rows)] == list(lib.quintile)


def test_a_duplicated_join_key_resolves_to_its_last_track():
    """Remix and feat. variants share a join key. The pipeline resolves a key
    to the last track holding it, so the earlier one is never a seed and never
    a positive -- and the SQL must agree, or seed counts drift apart."""
    songs = [
        song("Strategy (feat. Megan Thee Stallion)", "TWICE"),
        song("Strategy", "TWICE"),
        song("Hype Boy", "NewJeans"),
        song("Ditto", "NewJeans"),
    ]
    gt = {"twice::strategy": ["newjeans::hype boy"], "newjeans::hype boy": ["twice::strategy"]}
    conn = tiny(songs, gt, repeats=1)
    got = {r["seed_id"]: r["n_positives"] for r in conn.execute("SELECT * FROM evaluable_seed")}
    assert got == {i: len(p) for i, p in evaluable_seeds(gt, songs).items()} == {1: 1, 2: 1}


def test_serviceability_matches_can_serve(sample):
    songs, gt, conn = sample
    lib = Library(songs)
    got = {(r["policy"], r["seed_id"]): bool(r["served"]) for r in conn.execute("SELECT * FROM served")}
    want = {(p, i): can_serve(p, lib, i) for i in evaluable_seeds(gt, songs) for p in POLICIES}
    assert got == want


# ── Metrics ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def harness(sample):
    """What evaluate.py computes per seed, on the same sample and draws."""
    songs, gt, _ = sample
    return load_script("evaluate").run(Library(songs), songs, gt, 0, REPEATS)


def test_every_seed_metric_matches_the_harness(sample, harness):
    """Recall, precision, hit rate and NDCG at every k, for every policy on
    every seed -- the SQL re-derivation of metrics.evaluate_ranking, including
    zero for the seeds a policy cannot serve and the random floor's draws."""
    _, _, conn = sample
    sql = {(r["policy"], r["seed_id"], r["k"]): r for r in conn.execute("SELECT * FROM seed_metrics")}
    assert len(sql) == len(harness) * 4
    for row in harness.itertuples():
        for k in (5, 10, 20, 50):
            got = sql[(row.policy, row.seed_index, k)]
            assert bool(got["served"]) == row.served
            for m in METRIC_NAMES:
                assert got[m] == pytest.approx(harness.at[row.Index, f"{m}@{k}"], abs=EXACT)


def test_artist_blind_metric_matches_the_harness(sample, harness):
    _, _, conn = sample
    sql = {(r["policy"], r["seed_id"], r["k"]): r["ndcg"] for r in conn.execute("SELECT * FROM seed_metrics_blind")}
    blind = harness[harness.blind_evaluable]
    assert len(sql) == len(blind) * 4
    for row in blind.itertuples():
        for k in (5, 10, 20, 50):
            assert sql[(row.policy, row.seed_index, k)] == pytest.approx(
                harness.at[row.Index, f"blind_ndcg@{k}"], abs=EXACT)


def test_a_list_too_short_to_score_is_unknown_not_zero(sample):
    """Filtering out the seed's artist can leave fewer than k stored tracks.
    Scoring that as if the missing slots were misses would bias the blind
    variant downward; the view must refuse instead."""
    _, _, conn = sample
    policy, seed = conn.execute(
        "SELECT r.policy, r.seed_id FROM rankings r "
        "JOIN tracks s ON s.track_id = r.seed_id JOIN tracks c ON c.track_id = r.track_id "
        "JOIN served v ON v.policy = r.policy AND v.seed_id = r.seed_id AND v.served "
        "WHERE r.draw = 0 AND r.rank <= 10 AND c.artist_id = s.artist_id LIMIT 1"
    ).fetchone()
    conn.execute("SAVEPOINT truncate")
    conn.execute("DELETE FROM rankings WHERE policy = ? AND seed_id = ? AND rank > 10", (policy, seed))
    got = conn.execute("SELECT ndcg FROM seed_metrics_blind WHERE policy = ? AND seed_id = ? AND k = 10",
                       (policy, seed)).fetchone()[0]
    conn.execute("ROLLBACK TO truncate")
    conn.execute("RELEASE truncate")
    assert got is None


# ── Statistics SQLite has no function for ───────────────────────────────────

def test_regression_closed_form_matches_lstsq(sample):
    """The novelty-vs-obscurity coefficients, from three correlations in SQL,
    against numpy's least squares on the same standardized variables."""
    _, _, conn = sample
    df = load_script("analyze_tag_sparsity").to_frame(config.SONGS_SAMPLE_JSON)
    d = df.dropna(subset=["year", "listeners"])
    d = d[d["year"].between(1990, 2026) & (d["listeners"] > 0)]
    z = lambda x: (np.asarray(x, float) - np.mean(x)) / np.std(x)  # noqa: E731
    yr, pop, y = z(d["year"]), z(np.log10(d["listeners"])), z(d["n_eff"])
    X = np.column_stack([np.ones(len(d)), yr, pop])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    r2 = 1 - (y - X @ beta).var() / y.var()

    got = db.check(conn, "novelty_vs_obscurity")[0]
    assert got["n_tracks"] == len(d)
    assert got["beta_year"] == pytest.approx(beta[1], abs=1e-9)
    assert got["beta_pop"] == pytest.approx(beta[2], abs=1e-9)
    assert got["r2"] == pytest.approx(r2, abs=1e-9)
    assert got["r_year"] == pytest.approx(np.corrcoef(yr, y)[0, 1], abs=1e-9)


def test_window_medians_and_percentiles_match_numpy(sample):
    """Median and linear-interpolated percentiles written with ROW_NUMBER,
    on both odd and even counts, against numpy."""
    songs, gt, conn = sample
    first = [s["listeners"] for s in songs if not s.get("tag_source")]
    back = [s["listeners"] for s in songs if s.get("tag_source") == "backfill"]
    got = db.check(conn, "selection_bias")[0]
    assert (got["first_pass_median"], got["backfill_median"]) == (np.median(first), np.median(back))

    n_pos = [len(v) for v in gt.values()]
    got = {r["labels"]: r for r in db.check(conn, "gt_density")}["all"]
    assert got["median_positives"] == pytest.approx(np.median(n_pos))
    assert got["p75_positives"] == pytest.approx(np.percentile(n_pos, 75))


def test_an_even_count_takes_the_mean_of_the_middle_two():
    """Both sample groups happen to have odd sizes, so the case where the
    median is not a row of the table needs its own library."""
    songs = [song(f"f{i}", listeners=v) for i, v in enumerate((10, 20, 30, 40))]
    songs += [dict(song(f"b{i}", listeners=v), tag_source="backfill") for i, v in enumerate((1, 4))]
    got = db.check(tiny(songs), "selection_bias")[0]
    assert (got["first_pass_median"], got["backfill_median"]) == (25, 2.5)


# ── End to end ──────────────────────────────────────────────────────────────

def test_the_sample_reports_survive_the_cross_check(tmp_path):
    """What `make sqlcheck` does, in a scratch directory: generate the sample
    reports with pandas, build the database, and recompute every number in
    them in SQL. Any mismatch exits non-zero."""
    py = sys.executable
    run = lambda *a: subprocess.run([py, *map(str, a)], cwd=ROOT, capture_output=True, text=True)  # noqa: E731
    for step in (
        ("scripts/analyze_tag_sparsity.py", "--songs", config.SONGS_SAMPLE_JSON,
         "--outdir", tmp_path, "--figdir", tmp_path),
        ("scripts/evaluate.py", "--outdir", tmp_path, "--figdir", tmp_path),
        ("scripts/build_db.py", "--out", tmp_path / "sample.db"),
    ):
        assert run(*step).returncode == 0, step[0]
    res = run("scripts/sql_crosscheck.py", "--db", tmp_path / "sample.db", "--reports", tmp_path)
    assert res.returncode == 0, res.stdout
    assert "0 mismatched" in res.stdout
