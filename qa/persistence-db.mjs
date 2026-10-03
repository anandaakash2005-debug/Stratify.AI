import { PGlite } from '@electric-sql/pglite';
import fs from 'node:fs';
import assert from 'node:assert/strict';
const db=new PGlite();
try {
 await db.exec(`CREATE ROLE anon; CREATE ROLE authenticated; CREATE ROLE service_role;
 CREATE SCHEMA auth; CREATE TABLE auth.users(id uuid PRIMARY KEY,email text);
 CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS 'SELECT nullif(current_setting(''request.jwt.claim.sub'',true),'''')::uuid';`);
 await db.exec(fs.readFileSync('backend/database/schema.sql','utf8'));
 await db.exec(fs.readFileSync('backend/database/analysis_pipeline.sql','utf8'));
 // Migration is repeatable.
 await db.exec(fs.readFileSync('backend/database/analysis_pipeline.sql','utf8'));
 const chatHistoryMigration=fs.readFileSync('backend/database/chat_history.sql','utf8');
 await db.exec(chatHistoryMigration);
 await db.exec(chatHistoryMigration);
 assert.equal((await db.query("SELECT count(*)::int AS n FROM pg_policies WHERE schemaname='public' AND tablename='chat_history'")).rows[0].n,2);
 const user='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', other='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';
 const request='cccccccc-cccc-4ccc-8ccc-cccccccccccc',owner='dddddddd-dddd-4ddd-8ddd-dddddddddddd';
 await db.query('INSERT INTO auth.users VALUES ($1,$2),($3,$4)',[user,'test@example.invalid',other,'other@example.invalid']);
 async function rpc(name,args) {const r=await db.query(`SELECT ${name}(${args.map((_,i)=>'$'+(i+1)).join(',')}) AS data`,args);return r.rows[0].data;}
 // Reproduce the old writer's foreign-key failure: auth user exists but public profile does not.
 await assert.rejects(db.query('INSERT INTO startups(user_id,name,idea,market,business_model,target_audience) VALUES ($1,$2,$3,$4,$5,$6)',
   [user,'Legacy writer','Test','SaaS','Subscription','Retailers']),e=>e.code==='23503');
 assert.equal((await rpc('claim_analysis',[user,request,'hash',owner])).status,'claimed');
 assert.equal((await rpc('claim_analysis',[user,request,'hash',other])).status,'processing');
 assert.equal((await rpc('claim_analysis',[user,request,'different',owner])).status,'conflict');
 const report=JSON.parse(fs.readFileSync('qa/report-fixture.json','utf8'));
 const form=report._form_data;
 const result=await rpc('finish_analysis',[user,request,owner,form,report]);
 assert.equal((await rpc('claim_analysis',[user,request,'hash',owner])).result.report_id,result.report_id);
 assert.equal((await rpc('finish_analysis',[user,request,owner,form,report])).report_id,result.report_id);
 let counts=(await db.query('SELECT (SELECT count(*) FROM startups) startups,(SELECT count(*) FROM reports) reports,(SELECT count(*) FROM scores) scores')).rows[0];
 assert.deepEqual(counts,{startups:1,reports:1,scores:1});
 // Genuine new request reuses the startup, creates another report.
 await rpc('claim_analysis',[user,other,'hash',owner]);
 await rpc('finish_analysis',[user,other,owner,form,report]);
 counts=(await db.query('SELECT (SELECT count(*) FROM startups) startups,(SELECT count(*) FROM reports) reports')).rows[0];
 assert.deepEqual(counts,{startups:1,reports:2});
 // A score failure rolls back both the report and newly inserted startup.
 const third='eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee';
 await rpc('claim_analysis',[user,third,'hash',owner]);
 const bad=structuredClone(report); bad.metrics.survival_score='invalid';
 await assert.rejects(rpc('finish_analysis',[user,third,owner,{...form,startup_name:'Rollback fixture'},bad]));
 assert.equal((await db.query('SELECT count(*) n FROM reports')).rows[0].n,2);
 assert.equal((await db.query('SELECT count(*) n FROM startups')).rows[0].n,1);
 await rpc('release_analysis',[user,third,owner]);
 assert.equal((await rpc('claim_analysis',[user,third,'hash',other])).status,'claimed');
 // Unauthorized users see no rows; owners can read their own data.
 await db.exec('GRANT USAGE ON SCHEMA public,auth TO authenticated; GRANT SELECT ON ALL TABLES IN SCHEMA public TO authenticated; SET ROLE authenticated;');
 await db.query("SELECT set_config('request.jwt.claim.sub',$1,false)",[other]);
 assert.equal((await db.query('SELECT count(*) n FROM reports')).rows[0].n,0);
 await db.query("SELECT set_config('request.jwt.claim.sub',$1,false)",[user]);
 assert.equal((await db.query('SELECT count(*) n FROM reports')).rows[0].n,2);
 console.log('PASS: migration, duplicate claim, payload conflict, transactional report/score persistence, replay, startup reuse, user ownership RLS.');
} finally {await db.close();}
