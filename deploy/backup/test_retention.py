import datetime as dt
import unittest

from retention import select_delete, select_keep


def name(day: dt.date, hour: int = 3) -> str:
    return f"ragconsumer-{day:%Y%m%d}T{hour:02d}0000Z.tar.age"


NOW = dt.datetime(2026, 11, 13, 12, 0, tzinfo=dt.timezone.utc)


def nightly(days: int) -> list[str]:
    return [name(NOW.date() - dt.timedelta(days=i)) for i in range(days)]


class RetentionTests(unittest.TestCase):
    def test_keeps_everything_inside_the_daily_window(self):
        names = nightly(14)
        self.assertEqual(select_delete(names, NOW), [])

    def test_old_nightlies_are_thinned_to_weekly_and_monthly(self):
        names = nightly(400)
        kept = select_keep(names, NOW)
        self.assertTrue(set(nightly(14)) <= kept)
        # at most 14 daily + 8 weekly + 12 monthly
        self.assertLessEqual(len(kept), 14 + 8 + 12)
        self.assertGreater(len(kept), 14 + 7)
        # nothing older than the monthly window survives
        cutoff = name(dt.date(2025, 10, 1))
        self.assertTrue(all(n >= cutoff for n in kept))

    def test_first_backup_of_each_month_is_kept(self):
        names = nightly(200)
        kept = select_keep(names, NOW)
        for month in (5, 6, 7, 8, 9):
            first = min(n for n in names if n[len("ragconsumer-"):len("ragconsumer-") + 6] == f"2026{month:02d}")
            self.assertIn(first, kept)

    def test_newest_is_never_deleted_even_when_ancient(self):
        names = [name(dt.date(2020, 1, 1)), name(dt.date(2020, 1, 2))]
        self.assertIn(name(dt.date(2020, 1, 2)), select_keep(names, NOW))

    def test_other_files_are_ignored(self):
        names = nightly(3) + ["notes.txt", "last-success", "ragconsumer-bad.tar.age"]
        self.assertEqual(select_delete(names, NOW), [])
        self.assertNotIn("notes.txt", select_keep(names, NOW))

    def test_empty(self):
        self.assertEqual(select_keep([], NOW), set())
        self.assertEqual(select_delete([], NOW), [])

    def test_several_backups_in_one_day_all_kept_while_recent(self):
        names = [name(NOW.date(), 1), name(NOW.date(), 13)]
        self.assertEqual(select_delete(names, NOW), [])


if __name__ == "__main__":
    unittest.main()
