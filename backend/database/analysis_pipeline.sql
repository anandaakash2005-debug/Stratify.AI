-- Satquery.AI analysis persistence migration.
-- Creates the idempotency/lease table, atomic persistence functions, score columns,
-- and authenticated ownership policies required by POST /api/v1/analyze/.
-- Safe to rerun: it uses IF NOT EXISTS, CREATE OR REPLACE, and named policy replacement;
-- it does not drop tables or delete user data. Apply it after schema.sql in Supabase:
-- Dashboard -> SQL Editor -> New query -> paste this file -> Review -> Run.
-- Invariant: the database lease (600 seconds) exceeds the complete analysis timeout (480 seconds).
BEGIN;
CREATE TABLE IF NOT EXISTS public.analysis_requests (
 user_id uuid NOT NULL REFERENCES auth.users(id), request_id uuid NOT NULL,
 input_hash text NOT NULL, owner uuid NOT NULL, status text NOT NULL,
 lease_until timestamptz NOT NULL, result jsonb,
 PRIMARY KEY(user_id, request_id)
);
ALTER TABLE public.analysis_requests ADD COLUMN IF NOT EXISTS input_hash text;
ALTER TABLE public.analysis_requests ADD COLUMN IF NOT EXISTS owner uuid;
ALTER TABLE public.analysis_requests ADD COLUMN IF NOT EXISTS status text;
ALTER TABLE public.analysis_requests ADD COLUMN IF NOT EXISTS lease_until timestamptz;
ALTER TABLE public.analysis_requests ADD COLUMN IF NOT EXISTS result jsonb;
ALTER TABLE public.analysis_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.scores ADD COLUMN IF NOT EXISTS funding_readiness numeric;
ALTER TABLE public.scores ADD COLUMN IF NOT EXISTS runway_months numeric;
ALTER TABLE public.scores ADD COLUMN IF NOT EXISTS revenue_growth numeric;
ALTER TABLE public.scores ADD COLUMN IF NOT EXISTS burn_multiple numeric;
ALTER TABLE public.scores ADD COLUMN IF NOT EXISTS risk_count integer;

CREATE OR REPLACE FUNCTION public.claim_analysis(p_user uuid, p_request uuid, p_hash text, p_owner uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE r public.analysis_requests;
BEGIN
 INSERT INTO public.analysis_requests (
  user_id, request_id, input_hash, owner, status, lease_until, result
 ) VALUES (
  p_user, p_request, p_hash, p_owner, 'processing', now() + interval '600 seconds', null
 )
 ON CONFLICT DO NOTHING;
 SELECT * INTO r FROM public.analysis_requests WHERE user_id=p_user AND request_id=p_request FOR UPDATE;
 IF r.input_hash <> p_hash THEN RETURN jsonb_build_object('status','conflict'); END IF;
 IF r.status='complete' THEN RETURN jsonb_build_object('status','complete','result',r.result); END IF;
 IF r.owner<>p_owner AND r.status='processing' AND r.lease_until>now() THEN
  RETURN jsonb_build_object('status','processing');
 END IF;
 UPDATE public.analysis_requests SET owner=p_owner,status='processing',lease_until=now()+interval '600 seconds'
 WHERE user_id=p_user AND request_id=p_request;
 RETURN jsonb_build_object('status','claimed');
END $$;

CREATE OR REPLACE FUNCTION public.release_analysis(p_user uuid,p_request uuid,p_owner uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
 UPDATE public.analysis_requests SET status='failed',lease_until=now()
 WHERE user_id=p_user AND request_id=p_request AND owner=p_owner AND status='processing';
 RETURN '{}'::jsonb;
END $$;

CREATE OR REPLACE FUNCTION public.finish_analysis(p_user uuid,p_request uuid,p_owner uuid,p_form jsonb,p_result jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE r public.analysis_requests; sid uuid; rid uuid; v_result jsonb; m jsonb;
BEGIN
 SELECT * INTO r FROM public.analysis_requests WHERE user_id=p_user AND request_id=p_request FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Missing request claim'; END IF;
 IF r.status='complete' THEN RETURN r.result; END IF;
 IF r.owner<>p_owner OR r.status<>'processing' OR r.lease_until<=now() THEN
  RAISE EXCEPTION 'Request lease expired';
 END IF;
 -- Serialize startup reuse for this user across different request IDs.
 PERFORM pg_advisory_xact_lock(hashtextextended(p_user::text,0));
 -- Existing schema references public.users, not auth.users. Ensure the profile exists.
 INSERT INTO public.users(id,email) SELECT id,email FROM auth.users WHERE id=p_user
 ON CONFLICT(id) DO NOTHING;
 SELECT id INTO sid FROM public.startups WHERE user_id=p_user AND name=p_form->>'startup_name'
 ORDER BY created_at LIMIT 1;
 IF sid IS NULL THEN
  INSERT INTO public.startups(user_id,name,idea,market,business_model,target_audience,stage)
  VALUES(p_user,p_form->>'startup_name',coalesce(p_form->>'description',p_form->>'startup_idea',''),
   coalesce(p_form->>'industry',p_form->>'market',''),coalesce(p_form->>'business_model',''),
   coalesce(p_form->>'target_audience',''),coalesce(p_form->>'stage','idea')) RETURNING id INTO sid;
 END IF;
 rid := gen_random_uuid();
 v_result := p_result || jsonb_build_object('report_id',rid,'startup_id',sid,'request_id',p_request);
 INSERT INTO public.reports(id,startup_id,report_type,raw_ai_response,swot,risks,competitors,recommendations)
 VALUES(rid,sid,'full',v_result,v_result->'swot',v_result->'risks',v_result->'competitors',v_result->'recommendations');
 m := v_result->'metrics';
 INSERT INTO public.scores(startup_id,report_id,health_score,funding_readiness,team_score,market_score,
 runway_months,revenue_growth,burn_multiple,risk_count)
 VALUES(sid,rid,(m->>'survival_score')::numeric,(m->>'funding_readiness')::numeric,
 (m->>'team_score')::numeric,(m->>'market_score')::numeric,(m->>'runway_months')::numeric,
 coalesce(nullif(p_form->>'revenue_growth',''),'0')::numeric,
 (m->>'burn_multiple')::numeric,(m->>'risk_count')::integer);
 UPDATE public.analysis_requests SET status='complete',result=v_result
 WHERE user_id=p_user AND request_id=p_request;
 RETURN v_result;
END $$;

REVOKE ALL ON FUNCTION public.claim_analysis(uuid,uuid,text,uuid) FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.release_analysis(uuid,uuid,uuid) FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.finish_analysis(uuid,uuid,uuid,jsonb,jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.claim_analysis(uuid,uuid,text,uuid) TO service_role;
GRANT EXECUTE ON FUNCTION public.release_analysis(uuid,uuid,uuid) TO service_role;
GRANT EXECUTE ON FUNCTION public.finish_analysis(uuid,uuid,uuid,jsonb,jsonb) TO service_role;

-- Restrictive ownership guards also constrain any pre-existing permissive policies.
DO $$
DECLARE t text; expression text;
BEGIN
 FOREACH t IN ARRAY ARRAY['users','startups','reports','scores','analysis_requests'] LOOP
  expression := CASE WHEN t='users' THEN 'id=auth.uid()'
    WHEN t IN ('startups','analysis_requests') THEN 'user_id=auth.uid()'
    ELSE 'EXISTS (SELECT 1 FROM public.startups s WHERE s.id=startup_id AND s.user_id=auth.uid())' END;
  EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY',t);
  EXECUTE format('DROP POLICY IF EXISTS analysis_owner_guard ON public.%I',t);
  EXECUTE format('CREATE POLICY analysis_owner_guard ON public.%I AS RESTRICTIVE FOR ALL TO public USING (%s) WITH CHECK (%s)',t,expression,expression);
  EXECUTE format('DROP POLICY IF EXISTS analysis_owner_read ON public.%I',t);
  EXECUTE format('CREATE POLICY analysis_owner_read ON public.%I FOR SELECT TO authenticated USING (%s)',t,expression);
 END LOOP;
END $$;

GRANT USAGE ON SCHEMA public TO authenticated, service_role;
GRANT SELECT ON public.users, public.startups, public.reports, public.scores TO authenticated;
GRANT ALL ON public.analysis_requests TO service_role;
GRANT ALL ON public.users, public.startups, public.reports, public.scores TO service_role;
COMMIT;
