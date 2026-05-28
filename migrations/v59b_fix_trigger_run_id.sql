-- Fix: update_field_label_on_correction trigger was referencing enriched_field_log.run_id
-- but the correct column name is enrichment_run_id
-- Apply via Supabase SQL Editor

CREATE OR REPLACE FUNCTION update_field_label_on_correction()
RETURNS TRIGGER AS $$
BEGIN
    -- Mark the enriched_field_log entry as corrected
    -- FIX: was "WHERE run_id = NEW.run_id" — enriched_field_log column is enrichment_run_id
    UPDATE enriched_field_log
    SET field_label = 'corrected',
        label_source = 'kyle_correction',
        correction_id = NEW.id,
        reviewed_at = NOW()
    WHERE enrichment_run_id = NEW.run_id
      AND field_name = NEW.field_name
      AND entity_id = NEW.entity_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
