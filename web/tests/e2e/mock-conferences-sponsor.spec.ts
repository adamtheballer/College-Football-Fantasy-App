import {expect,test,type Page} from '@playwright/test';
import {canonicalDraftPool} from './fixtures/draft-pool';
const youtube='https://www.youtube.com/channel/UCQatEELNJL5GWry7eMXh-Qg?utm_source=chatgpt.com';
const sponsor={name:'Pigskin Dispatch',label:'Sponsored by Pigskin Dispatch',tagline:'Football history, stories & podcasts',logo_url:'/assets/sponsors/PigskinDispatchLogo.png',youtube_url:youtube,season:2026,week:8};
const players=[
 {id:1,name:'Texas Mock',school:'Texas',position:'QB',board_rank:1,sheet_projected_season_points:250,conference:'SEC'},
 {id:2,name:'Miami Mock',school:'Miami',position:'RB',board_rank:2,sheet_projected_season_points:220,conference:'ACC'},
 {id:3,name:'Ohio Mock',school:'Ohio State',position:'WR',board_rank:3,sheet_projected_season_points:210,conference:'BIG10'},
 {id:4,name:'Arizona Mock',school:'Arizona',position:'TE',board_rank:4,sheet_projected_season_points:200,conference:'BIG12'},
 {id:5,name:'Notre Dame Mock',school:'Notre Dame',position:'K',board_rank:5,sheet_projected_season_points:180,conference:'INDEPENDENT'},
];
function challenge(week:number) {return {id:81,round_id:week,kind:'lock',name:'Lock of the Week',state:'Upcoming',settlement_status:'draft',version:1,rules_version:'weekly-v1',rules:'Choose one winner.',lock_at:null,server_now:'2026-10-17T12:00:00Z',published_at:null,games:[],players:[],underdogs:[],entry:null,featured_game_id:null,scoring_rules:null,scoring_version:null,cancellation_reason:null,draft_config:null,sponsor:week===8?sponsor:null};}
function round(week:number) {return {id:week,season:2026,week,state:'Upcoming',next_rollover_at:'2026-10-28T12:00:00Z',server_now:'2026-10-17T12:00:00Z',challenges:[challenge(week)],sponsor:week===8?sponsor:null};}
async function fixture(page:Page, wrongBackend=false) {
 await page.addInitScript(()=>{
  localStorage.setItem('cfb_user',JSON.stringify({id:99111,firstName:'Conference QA',email:'conference@example.invalid'}));
  localStorage.setItem('cfb_access_token','isolated-conference-fixture');localStorage.setItem('cfb_access_token_expires_at','2030-01-01T00:00:00Z');localStorage.setItem('cfb_completed_guide_99111','true');
 });
 await page.route('**/api/**',async route=>{
  const url=new URL(route.request().url()),path=url.pathname.replace(/^\/api/,'');let body:unknown={data:[],total:0};
  if(path==='/auth/me') body={id:99111,first_name:'Conference QA',email:'conference@example.invalid'};
  else if(path.includes('unread')) body={data:[],total_unread:0};
  else if(path==='/health/runtime') {await route.fulfill({status:503,json:{detail:'Isolated fixture'}});return;}
  else if(path==='/players') {
   const codes=url.searchParams.get('conference_codes')?.split(',');
   const pool=codes&&!wrongBackend?players.filter(p=>codes.includes(p.conference)):players;
   body=canonicalDraftPool(pool,codes&&!wrongBackend?{draft_conference_codes:codes}:{});
  }
  else if(path==='/weekly-challenges/current') body=round(8);
  else if(path==='/weekly-challenges/history') body=[round(7),round(8),round(9)];
  else if(path.startsWith('/weekly-challenges/rounds/')) body=round(Number(path.split('/').pop()));
  else if(path==='/weekly-challenges/challenges/81') body=challenge(8);
  await route.fulfill({status:200,json:body});
 });
}
for(const width of [390,1280]) {
 test(`mock conference choices scope and survive resume/reset ${width}px`,async({page},info)=>{
  await page.setViewportSize({width,height:900});await fixture(page);
  await page.goto('/draft');const choices=page.getByRole('region',{name:'Mock draft conferences'});
  for(const name of ['Big Ten','Big 12','Independent']) await choices.getByRole('button',{name,exact:true}).click();
  await expect(page.getByRole('link',{name:/Start Single-Player Mock/})).toHaveAttribute('href',/conferences=SEC,ACC/);
  await page.screenshot({path:info.outputPath('mock-conference-setup.png')});
  await page.getByRole('link',{name:/Start Single-Player Mock/}).click();
  await expect(page.getByTestId('draft-player-row')).toHaveCount(2);
  await expect(page.getByTestId('draft-player-row').nth(0)).toContainText('Texas Mock');
  await expect(page.getByTestId('draft-player-row').nth(1)).toContainText('Miami Mock');
  await expect(page.getByLabel('Mock conference pool')).toHaveText('SEC + ACC');
  expect(await page.evaluate(()=>JSON.parse(localStorage.getItem('cfb_single_player_mock_draft')!).settings.conferenceCodes)).toEqual(['SEC','ACC']);
  await page.reload();await expect(page.getByLabel('Mock conference pool')).toHaveText('SEC + ACC');
  const reset=width<640?page.getByRole('button',{name:'Reset mock draft',exact:true}):page.getByRole('button',{name:'Reset',exact:true});
  await reset.click();await expect(page.getByTestId('draft-player-row')).toHaveCount(2);
  await expect(page.getByTestId('draft-player-row').filter({hasText:'Ohio Mock'})).toHaveCount(0);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 });
 test(`Week 8 sponsorship across home, list, detail, and historical boundaries ${width}px`,async({page},info)=>{
  await page.setViewportSize({width,height:900});await fixture(page);
  for(const path of ['/','/weekly-challenges','/weekly-challenges/81']) {
   await page.goto(path);
   const strip=page.getByRole('complementary',{name:'Week 8 sponsor'});
   await expect(strip).toHaveCount(1);await expect(strip).toContainText('Sponsored by Pigskin Dispatch');
   await expect(strip.getByRole('img',{name:'Pigskin Dispatch logo'})).toBeVisible();
   await expect.poll(() => strip.getByRole('img').evaluate((img:HTMLImageElement)=>img.complete&&img.naturalWidth>0)).toBe(true);
   await expect(strip.getByRole('link',{name:'Watch on YouTube'})).toHaveAttribute('href',youtube);
   expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  }
  await page.screenshot({path:info.outputPath('week8-sponsor-detail.png')});
  // Follow the actual external anchor without navigating away from the entry.
  // Initial popup navigation bypasses page.route; intercept at context level so CI needs no network.
  await page.context().route(youtube,route=>route.fulfill({status:200,body:'Channel destination verification'}));
  const popupPromise=page.waitForEvent('popup');await page.getByRole('link',{name:'Watch on YouTube'}).click();const popup=await popupPromise;
  await expect(popup).toHaveURL(youtube);await popup.close();
  for(const week of [7,9]) {await page.goto(`/weekly-challenges?round=${week}`);await expect(page.getByRole('heading',{name:'Weekly Challenges',exact:true})).toBeVisible();await expect(page.getByRole('complementary',{name:/sponsor/i})).toHaveCount(0);}
 });
}
test('a stale backend cannot silently start a full-pool mock for a restricted selection',async({page})=>{
 await fixture(page,true);await page.goto('/draft/mock/single-player?new=1&conferences=SEC');
 await expect(page.getByText(/selected mock conferences could not be verified/)).toBeVisible({timeout:15000});
 await expect(page.getByTestId('draft-player-row')).toHaveCount(0);
});
