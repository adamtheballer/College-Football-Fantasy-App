import {expect,test,type Page} from '@playwright/test';

async function shell(page:Page,width:number) {
 await page.setViewportSize({width,height:900});
 await page.clock.setFixedTime(new Date('2026-10-14T03:59:58Z'));
 await page.addInitScript(()=>{
  localStorage.setItem('cfb_user',JSON.stringify({id:999996,firstName:'Record QA',email:'record-ui@example.invalid',isAdmin:false}));
  localStorage.setItem('cfb_access_token','synthetic-record-ui');localStorage.setItem('cfb_access_token_expires_at','2030-01-01T00:00:00Z');localStorage.setItem('cfb_completed_guide_999996','true');
 });
 const state={phase:'applied',currentWeek:6,staleHistory:false};
 await page.route('**/api/**',async route=>{
  const url=new URL(route.request().url()),path=url.pathname.replace(/^\/api/,'');
  let body:unknown={data:[],total:0};
  if(path==='/auth/me') body={id:999996,first_name:'Record QA',email:'record-ui@example.invalid'};
  else if(path==='/health/runtime') body={git_sha:'synthetic-records',web_git_sha:'synthetic-records',worker_git_sha:'synthetic-records',api_process_instance_uuid:'synthetic-records',runtime_mode:'development',environment:'development',readiness_status:'ready',scoring_mode:'standard',sportsdata_enabled:false,ios_app_review_enabled:false};
  else if(path.includes('unread-count')) body={total_unread:0};
  else if(path.includes('preferences')) body={};
  else if(path==='/leagues/42') body={id:42,name:'Record QA League',season_year:2026,status:'post_draft',max_teams:2,draft:{status:'completed'},teams:[],settings:{roster_slots_json:{QB:1}}};
  else if(path==='/leagues/42/matchup') {
   const selected=Number(url.searchParams.get('week'))||state.currentWeek;
   const expired=state.currentWeek===7,history=selected===6;
   const certified=state.phase==='applied'||state.phase==='corrected';
   const color=certified&&!expired;
   const status=expired&&!history?'projected':state.phase==='live'?'live':state.phase==='corrected'?'stat_corrected':'final';
   const team=(id:number)=>({id,name:id===1?'Winner':'Loser',fantasy_team_id:id,fantasy_team_name:id===1?'Winner':'Loser',manager_name:id===1?'Winner':'Loser',record:id===1?(state.phase==='corrected'?'11-4-0':'12-3-0'):(state.phase==='corrected'?'4-11-0':'3-12-0'),record_highlight:color||(history&&state.staleHistory)?(id===1?(state.phase==='corrected'?'loss':'win'):(state.phase==='corrected'?'win':'loss')):null,current_points:id===1?100:90,projected_points:100,projected_total:100,win_probability:50,roster:[]});
   body={league_id:42,season:2026,week:selected,current_matchup_week:history&&state.staleHistory?6:state.currentWeek,matchup_id:selected===6?66:77,status,matchup_week_rollover_at:selected===6?'2026-10-14T04:00:00Z':'2026-10-21T04:00:00Z',my_team:team(1),user_team:team(1),opponent_team:team(2),my_roster:[],opponent_roster:[]};
  } else if(path==='/leagues/42/matchups') body={data:[],total:0};
  await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)});
 });
 return state;
}

for(const width of [1280,390]) {
 test(`applied records, refresh, correction and rollover ${width}px`,async({page},info)=>{
  const state=await shell(page,width);await page.goto('/league/42/matchup');
  const board=page.getByTestId('matchup-scoreboard');
  await expect(board.locator('[data-record-count="wins"]').first()).toHaveText('12');
  await expect(board.locator('[data-record-count="wins"]').first()).toHaveClass('text-emerald-300');
  await expect(board.locator('[data-record-count="losses"]').last()).toHaveClass('text-red-400');
  await expect(board.locator('[data-record-count="wins"]').first().locator('..')).toHaveText('12-3-0');
  await page.screenshot({path:info.outputPath('final-record-highlight.png'),animations:'disabled'});
  await page.reload();await expect(board.locator('.text-emerald-300[data-record-count]')).toHaveCount(1);
  state.phase='pending';await page.reload();await expect(board.locator('[data-record-count="wins"]').first()).toHaveText('12');
  await expect(board.locator('[data-record-count][class]')).toHaveCount(0);
  state.phase='live';await page.reload();await expect(board.locator('[data-record-count="wins"]').first()).toBeVisible();await expect(board.locator('[data-record-count][class]')).toHaveCount(0);
  state.phase='corrected';await page.reload();await expect(board.locator('[data-record-count="losses"]').first()).toHaveText('4');
  await expect(board.locator('[data-record-count="losses"]').first()).toHaveClass('text-red-400');
  await expect(board.locator('[data-record-count="wins"]').last()).toHaveClass('text-emerald-300');
  state.phase='applied';await page.reload();await expect(board.locator('.text-emerald-300[data-record-count]')).toHaveCount(1);
  // Exercise the already-mounted page's actual scheduled boundary and polling.
  state.currentWeek=7;await page.clock.setFixedTime(new Date('2026-10-14T04:00:00.100Z'));
  await expect(board.locator('[data-record-count][class]')).toHaveCount(0);
  await expect(board).toContainText('Week 7 matchup');
  // Replay a delayed old response whose own context still claims Week 6.
  state.staleHistory=true;await page.goto('/league/42/matchup?week=6&matchup=66');
  await expect(board).toContainText('Week 6 matchup');
  await expect(board.locator('[data-record-count][class]')).toHaveCount(0);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.screenshot({path:info.outputPath('expired-record-neutral.png'),animations:'disabled'});
 });
}
