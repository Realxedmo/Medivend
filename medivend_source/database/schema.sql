-- MediVend Supabase Schema
-- Run this in Supabase SQL Editor to set up all tables
-- Dashboard: https://supabase.com/dashboard/project/hdpbzflntprxnctucyfp

-- ─── USERS ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.users (
  user_id       SERIAL PRIMARY KEY,
  username      VARCHAR NOT NULL UNIQUE,
  password_hash VARCHAR NOT NULL,
  role          VARCHAR CHECK (role IN ('patient','pharmacist','admin')),
  created_at    TIMESTAMP DEFAULT now()
);

-- ─── DRUGS ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.drugs (
  drug_id              SERIAL PRIMARY KEY,
  brand_names          TEXT,
  classification       VARCHAR,
  dosage_form          VARCHAR,
  strengths            TEXT,
  contraindications    TEXT,
  side_effects         TEXT,
  drug_interactions    TEXT,
  usage_instructions   TEXT,
  source_url           VARCHAR,
  last_validated_date  DATE,
  created_at           TIMESTAMP DEFAULT now()
);

-- ─── INVENTORY ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.inventory (
  inventory_id      SERIAL PRIMARY KEY,
  drug_id           INT REFERENCES public.drugs(drug_id),
  quantity_in_stock INT CHECK (quantity_in_stock >= 0),
  expiry_date       DATE,
  reorder_threshold INT DEFAULT 10,
  batch_number      VARCHAR,
  last_updated      TIMESTAMP DEFAULT now()
);

-- ─── PRESCRIPTIONS ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.prescriptions (
  prescription_id    SERIAL PRIMARY KEY,
  user_id            INT REFERENCES public.users(user_id),
  image_storage_path VARCHAR,
  ocr_raw_text       TEXT,
  parsed_data        JSONB,
  validation_status  VARCHAR DEFAULT 'pending'
                     CHECK (validation_status IN ('pending','approved','rejected')),
  rejection_reason   TEXT,
  uploaded_at        TIMESTAMP DEFAULT now()
);

-- ─── SALES HISTORY ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.sales_history (
  sale_id       SERIAL PRIMARY KEY,
  drug_id       INT REFERENCES public.drugs(drug_id),
  quantity_sold INT NOT NULL,
  sale_date     DATE NOT NULL,
  source        VARCHAR DEFAULT 'real',
  created_at    TIMESTAMP DEFAULT now()
);

-- ─── PREDICTIONS ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.predictions (
  prediction_id           SERIAL PRIMARY KEY,
  drug_id                 INT REFERENCES public.drugs(drug_id) UNIQUE,
  predicted_demand        INT,
  predicted_stock_out_date DATE,
  confidence_score        FLOAT,
  model_version           VARCHAR,
  created_at              TIMESTAMP DEFAULT now()
);

-- ─── TRANSACTIONS ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.transactions (
  transaction_id   SERIAL PRIMARY KEY,
  user_id          INT REFERENCES public.users(user_id),
  drug_id          INT REFERENCES public.drugs(drug_id),
  quantity_dispensed INT CHECK (quantity_dispensed > 0),
  prescription_id  INT REFERENCES public.prescriptions(prescription_id),
  transaction_type VARCHAR,
  total_price      FLOAT,
  transaction_time TIMESTAMP DEFAULT now()
);

-- ─── MODEL METADATA ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.model_metadata (
  model_id     SERIAL PRIMARY KEY,
  model_name   VARCHAR UNIQUE,
  accuracy     FLOAT,
  mae          FLOAT,
  rmse         FLOAT,
  last_trained TIMESTAMP,
  notes        TEXT
);

-- ─── AUDIT LOGS ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.auditlogs (
  log_id      SERIAL PRIMARY KEY,
  timestamp   TIMESTAMP DEFAULT now(),
  user_id     INT REFERENCES public.users(user_id),
  action_type VARCHAR,
  details     JSONB
);

-- ─── ROW LEVEL SECURITY ────────────────────────────────────
-- Enable RLS on all tables
ALTER TABLE public.users          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.drugs          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.inventory      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.prescriptions  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sales_history  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.predictions    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.transactions   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.model_metadata ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.auditlogs      ENABLE ROW LEVEL SECURITY;

-- Allow anon reads on drugs, inventory, predictions (public data)
CREATE POLICY "Public read drugs"       ON public.drugs          FOR SELECT USING (true);
CREATE POLICY "Public read inventory"   ON public.inventory      FOR SELECT USING (true);
CREATE POLICY "Public read predictions" ON public.predictions    FOR SELECT USING (true);
CREATE POLICY "Public read metadata"    ON public.model_metadata FOR SELECT USING (true);

-- Allow authenticated users to read/write prescriptions (their own)
CREATE POLICY "Users own prescriptions" ON public.prescriptions
  FOR ALL USING (auth.uid()::text = user_id::text);

-- Pharmacists can read all prescriptions
CREATE POLICY "Pharmacists see all" ON public.prescriptions
  FOR SELECT USING (
    EXISTS (SELECT 1 FROM public.users WHERE user_id = auth.uid()::int AND role IN ('pharmacist','admin'))
  );

-- Allow inserts for authenticated users
CREATE POLICY "Insert drugs"        ON public.drugs         FOR INSERT WITH CHECK (true);
CREATE POLICY "Update drugs"        ON public.drugs         FOR UPDATE USING (true);
CREATE POLICY "Insert inventory"    ON public.inventory     FOR INSERT WITH CHECK (true);
CREATE POLICY "Update inventory"    ON public.inventory     FOR UPDATE USING (true);
CREATE POLICY "Insert predictions"  ON public.predictions   FOR INSERT WITH CHECK (true);
CREATE POLICY "Upsert predictions"  ON public.predictions   FOR UPDATE USING (true);
CREATE POLICY "Insert sales"        ON public.sales_history FOR INSERT WITH CHECK (true);
CREATE POLICY "Read sales"          ON public.sales_history FOR SELECT USING (true);
CREATE POLICY "Insert audit"        ON public.auditlogs     FOR INSERT WITH CHECK (true);
CREATE POLICY "Read audit"          ON public.auditlogs     FOR SELECT USING (true);
CREATE POLICY "Read transactions"   ON public.transactions  FOR SELECT USING (true);
CREATE POLICY "Insert transactions" ON public.transactions  FOR INSERT WITH CHECK (true);
CREATE POLICY "Read users"          ON public.users         FOR SELECT USING (true);
CREATE POLICY "Insert users"        ON public.users         FOR INSERT WITH CHECK (true);

-- ─── SEED: INSERT DEMO USERS ───────────────────────────────
-- (Run separately after Supabase Auth setup)
-- INSERT INTO public.users (username, password_hash, role)
-- VALUES
--   ('Dr. Ahmed Hassan', '***', 'pharmacist'),
--   ('Sara Al-Khalidi',  '***', 'patient');
