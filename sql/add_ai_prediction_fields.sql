BEGIN;

ALTER TABLE public.properties
    ADD COLUMN IF NOT EXISTS ai_predicted_fields JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS ai_confidence JSONB NOT NULL DEFAULT '{}'::jsonb;

COMMENT ON COLUMN public.properties.ai_predicted_fields IS
    'Values inferred by the LLM from the property listing body text.';

COMMENT ON COLUMN public.properties.ai_confidence IS
    'Per-field confidence scores for values stored in ai_predicted_fields.';

COMMIT;
