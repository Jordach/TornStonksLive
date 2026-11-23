"""The /predict pipeline: causal features, anchor horizons and an honest skill score."""
import unittest

import numpy as np
import pandas as pd

from tsl_core.analysis import predict


def _ohlc_from_close(close, seed=0):
	rng = np.random.default_rng(seed)
	close = np.asarray(close, dtype=float)
	open_ = np.concatenate([[close[0]], close[:-1]])
	wick = np.abs(rng.normal(0, 0.002, len(close))) * close
	return pd.DataFrame({
		"Open": open_,
		"High": np.maximum(open_, close) + wick,
		"Low": np.minimum(open_, close) - wick,
		"Close": close,
	})


def _random_walk(n, seed=0):
	rng = np.random.default_rng(seed)
	return 500 * np.exp(np.cumsum(rng.normal(0, 0.003, n)))


class FeatureTests(unittest.TestCase):
	def test_features_are_causal(self):
		"""Row t must not change when later candles are added: no look-ahead."""
		df = _ohlc_from_close(_random_walk(400))
		full = predict.build_features(df)
		for t in (150, 260, 399):
			prefix = predict.build_features(df.iloc[:t + 1])
			pd.testing.assert_series_equal(prefix.iloc[-1], full.iloc[t], check_names=False, rtol=1e-9)

	def test_features_ignore_price_level(self):
		"""Scaling every price by a constant leaves the features unchanged."""
		df = _ohlc_from_close(_random_walk(300))
		scaled = df * 37.0
		a = predict.build_features(df).iloc[150:]
		b = predict.build_features(scaled).iloc[150:]
		np.testing.assert_allclose(a.values, b.values, rtol=1e-7, atol=1e-10)

	def test_m1_drops_constant_candle_features(self):
		df = _ohlc_from_close(_random_walk(200))
		self.assertIn("candle_body", predict.build_features(df).columns)
		self.assertNotIn("candle_body", predict.build_features(df, has_ohlc=False).columns)


class HorizonTests(unittest.TestCase):
	def test_anchor_horizons(self):
		self.assertEqual(predict.anchor_horizons(1), [1])
		self.assertEqual(predict.anchor_horizons(2), [1, 2])
		self.assertEqual(predict.anchor_horizons(48), [12, 24, 36, 48])
		self.assertEqual(predict.anchor_horizons(10), [3, 5, 8, 10])


class ForecastTests(unittest.TestCase):
	def test_path_starts_at_zero_and_has_one_point_per_step(self):
		df = _ohlc_from_close(_random_walk(1500, seed=1))
		path, metrics = predict.forecast_returns(df, "h1", 12)
		self.assertEqual(len(path), 13)
		self.assertEqual(path[0], 0.0)
		self.assertGreaterEqual(metrics["folds"], 2)

	def test_random_walk_shows_no_edge(self):
		"""A pure random walk is unpredictable; the score must not claim otherwise."""
		df = _ohlc_from_close(_random_walk(3000, seed=2))
		_, metrics = predict.forecast_returns(df, "h1", 10)
		self.assertLess(metrics["skill"], 0.05)

	def test_predictable_series_shows_skill(self):
		"""A smooth cycle is predictable from its own momentum, so skill should be clear."""
		t = np.arange(3000)
		rng = np.random.default_rng(3)
		close = 500 * np.exp(0.05 * np.sin(t / 40) + rng.normal(0, 0.0005, len(t)))
		_, metrics = predict.forecast_returns(_ohlc_from_close(close), "h1", 10)
		self.assertGreater(metrics["skill"], 0.3)
		self.assertGreater(metrics["direction_accuracy"], metrics["direction_baseline"])

	def test_long_horizons_request_more_samples(self):
		self.assertGreater(predict.required_samples(200), predict.required_samples(10))


if __name__ == "__main__":
	unittest.main()
