import {expect,test,type Page} from '@playwright/test';

async function publicStatsShell(page:Page) {
   // Simulate only the shell session; no real account login or password.
   // All player/card/game-log requests reach the actual public local API.
   await page.addInitScript(()=>{
    localStorage.setItem('cfb_user',JSON.stringify({id:999999,firstName:'Stats QA',email:'fixture@example.invalid',isAdmin:false}));
    localStorage.setItem('cfb_access_token','public-stats-fixture');localStorage.setItem('cfb_access_token_expires_at','2030-01-01T00:00:00Z');localStorage.setItem('cfb_completed_guide_999999','true');
   });
   await page.route('**/api/**',async route=>{
    const path=new URL(route.request().url()).pathname.replace(/^\/api/,'');
    if(['/players','/injuries','/stats','/projections','/health'].some(prefix=>path.startsWith(prefix))) {
     const headers={...route.request().headers()};delete headers.authorization;
     await route.continue({headers});return;
    }
    const body=path==='/auth/me'?{id:999999,first_name:'Stats QA',email:'fixture@example.invalid'}:path.includes('preferences')?{}:{data:[],total:0};
    await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)});
   });
}

test.describe('Source-backed local player stats and full-height shell',()=>{
 test.skip(process.env.CFF_PLAYER_STATS_E2E!=='1','Requires isolated local accounts and verified ESPN cache replay');
 for(const width of [1280,390]) {
  test(`Alex Perry transfer history ${width}px`,async({page},info)=>{
   expect(['localhost','127.0.0.1']).toContain(new URL(process.env.E2E_BASE_URL!).hostname);
   await page.setViewportSize({width,height:900});
   await publicStatsShell(page);
   // No player/card/game-log response interception: actual local source-backed API.
   await page.goto('/injury-center?playerId=1082');const dialog=page.getByRole('dialog');await expect(dialog).toContainText('Alex Perry');
   await dialog.getByRole('button',{name:'Game Log',exact:true}).click();
   await expect(dialog.getByLabel('Game log season')).toHaveValue('2025');
   await expect(dialog.getByRole('region',{name:'2025 season summary'})).toContainText('840');
   await expect(dialog.getByRole('region',{name:'2025 season summary'})).toContainText('56');
   await expect(dialog.getByRole('region',{name:'2025 season summary'})).toContainText('Games with stats');
   await expect(dialog).toContainText('Verified performance for FIU in 2025.');
   const expected=[['Middle Tennessee','71'],['Liberty','88'],['Jacksonville State','109'],['Sam Houston','140'],['UTSA','24']] as const;
   for(const [opponent,yards] of expected) await expect(dialog.getByRole('row').filter({hasText:opponent})).toContainText(yards);
   const game=dialog.getByRole('row').filter({hasText:'Sam Houston'});await expect(game).toContainText('56–16');
   await expect(dialog.getByRole('row')).toHaveCount(14);
   await expect(dialog.getByRole('row').filter({hasText:'UTSA'})).toContainText('24');
   await page.screenshot({path:info.outputPath('alex-perry-verified-2025-games.png'),animations:'disabled'});
   expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
   await dialog.getByRole('button',{name:/close/i}).click();
   if(width>=1024) {
    const size=await page.locator('.cfb-shell-sidebar').evaluate(element=>({height:element.getBoundingClientRect().height,navBottom:element.querySelector('nav')!.getBoundingClientRect().bottom,lastBottom:element.querySelector('nav')!.lastElementChild!.getBoundingClientRect().bottom}));
    expect(size.height).toBe(900);expect(size.navBottom-size.lastBottom).toBeLessThanOrEqual(14);
   }
  });
 }
 for(const width of [1280,390]) for(const [id,position] of [[1639,'QB'],[1594,'RB'],[1241,'TE'],[1255,'K']] as const) {
  test(`Source stats ${position} ${width}px`,async({page},info)=>{
   await publicStatsShell(page);await page.setViewportSize({width,height:900});
   const source=await page.request.get(`/api/players/${id}/game-log?season=2025`);expect(source.status()).toBe(200);const body=await source.json();
   const verified=body.games.filter((game:{stats:unknown})=>game.stats);expect(verified.length).toBeGreaterThan(0);
   await page.goto(`/injury-center?playerId=${id}`);const dialog=page.getByRole('dialog');await expect(dialog).toContainText(body.player_name);
   await dialog.getByRole('button',{name:'Game Log',exact:true}).click();await dialog.getByLabel('Game log season').selectOption('2025');
   const rows=dialog.getByRole('row');await expect(rows).toHaveCount(body.games.length+1);
   await expect(dialog.getByRole('region',{name:'2025 season summary'})).toContainText('Games with stats');
   await expect(dialog).not.toContainText('No game log is available');
   expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
   await page.screenshot({path:info.outputPath(`${position}-verified-stats-${width}.png`),animations:'disabled'});
  });
 }

});
