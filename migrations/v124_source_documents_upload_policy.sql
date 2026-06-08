-- v124: allow Submit-Intel file uploads to the private source-documents bucket
-- Applied 2026-06-08 via Management API. Recorded here for provenance.
--
-- The Submit Intel form (anon role) needs to upload attached PDFs so they are
-- actually SAVED in Supabase. This grants INSERT (upload) only — no SELECT/UPDATE/
-- DELETE for anon, so licensed docs stay private. Viewing is done via backend-
-- generated signed URLs (see scripts/review_submitted_intel.py: sign_storage_url).
--
-- Bucket is also hardened: file_size_limit = 25MB, allowed_mime_types = application/pdf.

DROP POLICY IF EXISTS "anon_upload_source_documents" ON storage.objects;
CREATE POLICY "anon_upload_source_documents"
  ON storage.objects FOR INSERT TO anon
  WITH CHECK (bucket_id = 'source-documents');
