-- Migration v17: Add UNIQUE constraint on validation_tests.test_name
-- Applied: 2026-05-23
-- Context: Required for ON CONFLICT upserts when seeding Rule E3 (company_area_check) tests.
--          Previously tests could only be inserted, not idempotently upserted.

ALTER TABLE validation_tests
  ADD CONSTRAINT validation_tests_test_name_key UNIQUE (test_name);

-- Rule E3 tests (company_area_check) seeded separately via Python script.
-- 61 tests covering all company_profiles rows — each asserts that the
-- corresponding company_areas row exists (orphan profile detection).
