import {expect,test,type Page} from "@playwright/test";

async function publicChartShell(page:Page) {
  // Synthetic shell session only; public card requests reach the actual local
  // API. No real account, login, provider updates or production data writes.
  await page.addInitScript(()=>{
    localStorage.setItem("cfb_user",JSON.stringify({id:999998,firstName:"Chart QA",email:"fixture@example.invalid",isAdmin:false}));
    localStorage.setItem("cfb_access_token","public-chart-fixture");
    localStorage.setItem("cfb_access_token_expires_at","2030-01-01T00:00:00Z");
    localStorage.setItem("cfb_completed_guide_999998","true");
  });
  await page.route("**/api/**",async route=>{
    const path=new URL(route.request().url()).pathname.replace(/^\/api/,"");
    if(["/players","/injuries","/stats","/projections","/health"].some(prefix=>path.startsWith(prefix))) {
      const headers={...route.request().headers()};delete headers.authorization;
      await route.continue({headers});return;
    }
    await route.fulfill({json:path==="/auth/me"?{id:999998,first_name:"Chart QA",email:"fixture@example.invalid"}:path.includes("preferences")?{}:{data:[],total:0}});
  });
}

test.describe("Synthetic weekly chart transitions in the local player card",()=>{
  test.skip(process.env.CFF_CHART_E2E!=="1","Requires isolated local API and explicit synthetic chart fixtures");
  for(const width of [1280,390]) {
    test(`finalized/forecast/value refresh ${width}px`,async({page},info)=>{
      expect(["localhost","127.0.0.1"]).toContain(new URL(process.env.E2E_BASE_URL!).hostname);
      await page.setViewportSize({width,height:900});
      await publicChartShell(page);await page.clock.install();
      let finalWeek7=false;
      await page.route(/\/api\/players\/1082\/trajectory(?:\?|$)/,route=>route.fulfill({json:{player_id:1082,season:2026,league_id:null,projection:[
        {week:5,points:null,actual_points:-2,is_finalized:true,source:"actual",projection_status:"ACTUAL_ONLY"},
        {week:6,points:20,actual_points:18.4,is_finalized:true,source:"published",projection_status:"ACTIVE"},
        {week:7,points:21.2,actual_points:finalWeek7?24.6:null,is_finalized:finalWeek7,source:"published",projection_status:"ACTIVE"},
        ...(finalWeek7?[{week:8,points:23,actual_points:null,is_finalized:false,source:"published",projection_status:"ACTIVE"}]:[]),
      ],value:[{week:0,value:84,source:"preseason"},{week:5,value:57,source:"published"},{week:6,value:57.2,source:"published"},...(finalWeek7?[{week:7,value:58,source:"published"}]:[])]}}));
      await page.goto("/injury-center?playerId=1082");
      const dialog=page.getByRole("dialog");await expect(dialog).toContainText("Alex Perry");
      await dialog.getByRole("button",{name:"Projections",exact:true}).click();
      await expect(dialog.getByTestId("trajectory-projection-line")).toHaveAttribute("stroke-dasharray","7 7");
      await expect(dialog.getByTestId("trajectory-actual-line")).toHaveAttribute("stroke","#2f80ff");
      expect(await dialog.getByTestId("trajectory-actual-line").getAttribute("stroke-dasharray")).toBeNull();
      await expect(dialog.getByRole("button",{name:/Week 6 actual fantasy points.*18.4/})).toBeVisible();
      const week7=dialog.getByTestId("trajectory-point-week-7");await week7.click();
      await expect(week7).toHaveAttribute("aria-label",/Week 7 fantasy points.*Projected.*21.2/);
      const scroller=dialog.locator("svg[role='img']").locator("..");
      const scrollLeft=await scroller.evaluate(element=>element.scrollLeft);
      await page.screenshot({path:info.outputPath("synthetic-points-before-finalization.png"),animations:"disabled"});
      finalWeek7=true;
      await page.clock.runFor(31_000); // The real React Query background polling path.
      await expect(week7).toHaveAttribute("aria-label",/Week 7 actual fantasy points.*24.6.*Projected 21.2/);
      await expect(week7).toHaveAttribute("aria-pressed","true");
      await expect(dialog.getByTestId("trajectory-selected-point")).toContainText("Week 7 actual fantasy points (Finalized): 24.6 pts");
      await expect(dialog.getByTestId("trajectory-point-week-8")).toHaveAttribute("fill","#ffffff");
      await expect(dialog.getByTestId("trajectory-point-week-6")).toHaveAttribute("aria-label",/18.4/);
      expect(await scroller.evaluate(element=>element.scrollLeft)).toBe(scrollLeft);
      expect(await dialog.locator("svg circle[fill='#ffffff']").count()).toBe(1);
      expect(await dialog.getByTestId("trajectory-point-week-5").getAttribute("aria-label")).not.toContain("Projected");
      await page.screenshot({path:info.outputPath("synthetic-points-after-finalization.png"),animations:"disabled"});
      await dialog.getByRole("button",{name:"Value",exact:true}).click();
      await expect(dialog.getByTestId("trajectory-value-line")).toHaveAttribute("stroke","#2f80ff");
      expect(await dialog.getByTestId("trajectory-value-line").getAttribute("stroke-dasharray")).toBeNull();
      await expect(dialog.getByTestId("trajectory-point-week-6")).toHaveAttribute("aria-label",/57.2/);
      await page.screenshot({path:info.outputPath("synthetic-value-chart.png"),animations:"disabled"});
      expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    });
  }
});
