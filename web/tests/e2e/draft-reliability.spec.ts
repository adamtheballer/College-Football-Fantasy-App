import {canonicalDraftPool} from "./fixtures/draft-pool";
import { expect, test, type Page } from "@playwright/test";
import type { DraftRoom } from "../../client/types/draft";

const players = [
  { id: 501, name: "Arch Manning", position: "QB", school: "Texas", board_rank: 1, sheet_projected_season_points: 300 },
  { id: 502, name: "CJ Carr", position: "QB", school: "Notre Dame", board_rank: 2, sheet_projected_season_points: 280 },
];
const newRoom = (): DraftRoom => ({
  league_id: 77, draft_id: 21, draft_version: 1, status: "on_clock", pick_timer_seconds: 30,
  roster_slots: { QB: 1 }, teams: [
    { id: 1, name: "Your Team", owner_user_id: 42, owner_name: "Coach", is_cpu: false },
    { id: 2, name: "Other Team", owner_user_id: 43, owner_name: "Other", is_cpu: false },
  ], picks: [], current_pick: 1, current_round: 1, current_round_pick: 1,
  current_team_id: 1, current_team_name: "Your Team", user_team_id: 1,
  can_make_pick: true, can_start_draft: false, pre_draft_starts_at: null, draft_starts_at: null,
  current_pick_started_at: new Date().toISOString(), current_pick_deadline: new Date(Date.now() + 30_000).toISOString(),
  transition_ends_at: null, seconds_remaining: 30, pick_started_at: null, pick_expires_at: null, server_time: new Date().toISOString(),
});

async function fixture(page: Page, initialPlayers = players) {
  let currentPlayers = initialPlayers;
  let room = newRoom();
  let failing = false;
  let submissions = 0;
  let reject = false;
  let final = false;
  await page.addInitScript(() => {
    localStorage.setItem("cfb_user", JSON.stringify({ id: 42, firstName: "Coach", email: "draft-test@example.com" }));
    localStorage.setItem("cfb_access_token", "isolated-fixture-token");
    localStorage.setItem("cfb_access_token_expires_at", "2030-01-01T00:00:00Z");
    localStorage.setItem("cfb_completed_guide_42", "true");
  });
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace(/^\/api/, "");
    let data: unknown = { data: [], total: 0 };
    let status = 200;
    if (path === "/health/runtime") status = 503;
    if (path === "/auth/me") data = { id: 42, first_name: "Coach", email: "draft-test@example.com" };
    if (path === "/players") data = canonicalDraftPool(currentPlayers);
    if (/^\/players\/\d+$/.test(path)) data = currentPlayers.find(row => row.id === Number(path.split("/")[2]));
    if (/^\/players\/\d+\/card$/.test(path)) { status=404; data={detail:"No player card in this isolated draft fixture"}; }
    if (path === "/leagues/77") data = { id: 77, name: "Audit Test League", max_teams: 2, members: [{user_id:42},{user_id:43}], status: room.status === "completed" ? "post_draft" : "draft_live" };
    if (path === "/leagues/77/draft-room") {
      status = failing ? 503 : 200;
      data = failing ? { detail: "Temporarily unavailable" } : { ...room, server_time: new Date().toISOString() };
    }
    if (path === "/leagues/77/draft-picks") {
      submissions += 1;
      if (reject) { status = 409; data = { detail: "Pick expired; waiting for auto-pick" }; }
      else {
        const playerId = route.request().postDataJSON().player_id;
        const player = currentPlayers.find((row) => row.id === playerId)!;
        room = { ...room, draft_version: room.draft_version + 1, current_pick: 2, current_team_id: final ? null : 2,
          current_team_name: final ? null : "Other Team", can_make_pick: false, status: final ? "completed" : "on_clock",
          server_time: new Date().toISOString(), current_pick_deadline: final ? null : new Date(Date.now()+30_000).toISOString(),
          picks: [{ id: 100, overall_pick: 1, round_number: 1, round_pick: 1, team_id: 1, team_name: "Your Team", player_id: player.id,
            player_name: player.name, player_position: player.position, player_school: player.school, made_by_user_id: 42, auto_pick: false, created_at: new Date().toISOString() }],
        };
        data = room;
      }
    }
    await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(data) });
  });
  return {
    get room() { return room; },
    setPlayers(rows: typeof players) { currentPlayers = rows; },
    setRoom(value: Partial<DraftRoom>) { room = { ...room, ...value }; },
    setFailure(value: boolean) { failing = value; },
    reject() { reject = true; },
    finishOnPick() { final = true; },
    submissions: () => submissions,
  };
}

for (const width of [1440, 390]) {
  test(`real and mock sorts preserve ranks and player identity ${width}px`, async ({ page }, info) => {
    const pool = [
      {id:601,name:'Rank Two',position:'WR',school:'Texas',board_rank:1,sheet_projected_season_points:80,sheet_adp:2},
      {id:602,name:'Rank Ten',position:'WR',school:'Texas',board_rank:2,sheet_projected_season_points:100,sheet_adp:10},
      {id:603,name:'Rank Twenty',position:'WR',school:'Texas',board_rank:3,sheet_projected_season_points:0,sheet_adp:20},
      {id:604,name:'Rank 119',position:'WR',school:'Texas',board_rank:4,sheet_projected_season_points:70,sheet_adp:119},
    ];
    const state = await fixture(page,pool);
    state.setRoom({roster_slots:{WR:2,BENCH:5},current_pick_deadline:new Date(Date.now()+600_000).toISOString(),pick_timer_seconds:600});
    await page.setViewportSize({width,height:900});
    await page.addInitScript(now => localStorage.setItem('cfb_single_player_mock_draft',JSON.stringify({
      id:'sort-contract',settings:{leagueSize:4,rounds:13,pickTimerSeconds:120},status:'live',createdAt:now,intermissionEndsAt:now,currentPick:1,pickStartedAt:now,pickExpiresAt:now+600_000,userTeamId:1,
      teams:[{id:1,name:'Your Team',managerType:'user'},...Array.from({length:3},(_,i)=>({id:i+2,name:`Bot ${i+2}`,managerType:'bot'}))],picks:[],queuedPlayerIds:[604,601]
    })),Date.now());
    for(const route of ['/league/77/draft','/draft/mock/single-player']) {
      await page.goto(route);
      const rows=page.getByTestId('draft-player-row');
      await expect(rows).toHaveCount(4);
      await expect(rows.nth(0)).toContainText('Rank Two');
      await page.getByLabel('Draft board sort').selectOption('adp');
      for(const [i,name] of ['Rank Two','Rank Ten','Rank Twenty','Rank 119'].entries()) await expect(rows.nth(i)).toContainText(name);
      await page.getByLabel('Draft board sort').selectOption('projected_points');
      for(const [i,name] of ['Rank Ten','Rank Two','Rank 119','Rank Twenty'].entries()) await expect(rows.nth(i)).toContainText(name);
      await expect(rows.nth(3)).toContainText('0.0');
      await page.getByPlaceholder('Search players, schools...').fill('Rank 119');
      await expect(rows).toHaveCount(1);
      await expect(rows.nth(0).locator('p').first()).toHaveText('4');
      await page.getByPlaceholder('Search players, schools...').fill('');
      await expect(rows).toHaveCount(4);
      await page.screenshot({path:info.outputPath(`${route.includes('mock')?'mock':'real'}-sort-${width}.png`),animations:'disabled'});
      expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
      if(route.includes('mock')) expect(await page.evaluate(()=>JSON.parse(localStorage.getItem('cfb_single_player_mock_draft')!).queuedPlayerIds)).toEqual([604,601]);
    }
    await page.clock.install();
    await page.goto('/league/77/draft');
    const rows=page.getByTestId('draft-player-row');
    await expect(rows).toHaveCount(4);
    await rows.filter({hasText:'Rank Two'}).getByText('Rank Two',{exact:true}).click();
    await expect(page.getByRole('dialog')).toContainText('Rank Two');
    state.setPlayers([...pool].reverse().map((row,index)=>({...row,board_rank:index+1})));
    await page.clock.fastForward(61_000);
    await expect(rows.nth(0)).toContainText('Rank 119');
    await expect(page.getByRole('dialog')).toContainText('Rank Two');
    await page.getByRole('button',{name:'Close player card',exact:true}).click();
    await page.getByRole('button',{name:'Draft Rank Two',exact:true}).click();
    expect(state.room.picks[0].player_id).toBe(601);
    await expect(page.getByTestId('pick-confirmation')).toContainText('Rank Two');
  });
}

test("live expiry disables draft actions while preserving authoritative pick", async ({ page }, testInfo) => {
  const state = await fixture(page);
  state.setRoom({ current_pick_deadline: new Date(Date.now()-1000).toISOString() });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/league/77/draft");
  await expect(page.getByText("Time expired · Auto-pick pending", {exact:true})).toBeVisible();
  await expect(page.getByRole("button", {name:"Draft Arch Manning",exact:true})).toBeDisabled();
  await expect(page.getByTestId("pick-confirmation")).toHaveCount(0);
  expect(state.submissions()).toBe(0);
  expect(state.room.current_pick).toBe(1);
  await page.screenshot({path:testInfo.outputPath("draft-expired-mobile.png")});
});

test("confirmed pick animates once without moving list; next timer keeps running", async ({ page }, testInfo) => {
  const state = await fixture(page);
  await page.setViewportSize({width:390,height:844});
  await page.goto("/league/77/draft");
  const draft = page.getByRole("button", {name:"Draft Arch Manning",exact:true});
  await expect(draft).toBeEnabled();
  const height = await page.getByTestId("pick-context-strip").evaluate((e)=>e.getBoundingClientRect().height);
  await draft.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("pick-confirmation")).toHaveAttribute("data-phase","hold");
  await expect(page.getByTestId("pick-confirmation")).toContainText("Arch Manning");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByTestId("draft-player-row").filter({hasText:"Arch Manning"})).toHaveCount(0);
  const confirmationLayout = await page.evaluate(() => {
    const context = document.querySelector<HTMLElement>("[data-testid='pick-context-strip']");
    const confirmation = document.querySelector<HTMLElement>("[data-testid='pick-confirmation']");
    const portrait = confirmation?.querySelector<HTMLElement>("[aria-hidden='true']");
    if (!context || !confirmation || !portrait) return null;
    return {
      contextBottom: context.getBoundingClientRect().bottom,
      confirmationTop: confirmation.getBoundingClientRect().top,
      confirmationHeight: confirmation.getBoundingClientRect().height,
      confirmationBottom: confirmation.getBoundingClientRect().bottom,
      portraitTop: portrait.getBoundingClientRect().top,
      portraitBottom: portrait.getBoundingClientRect().bottom,
    };
  });
  expect(confirmationLayout).not.toBeNull();
  expect(Math.abs((confirmationLayout?.confirmationTop ?? 0) - (confirmationLayout?.contextBottom ?? 0))).toBeLessThanOrEqual(1);
  expect(confirmationLayout?.confirmationHeight).toBeGreaterThanOrEqual(90);
  expect(confirmationLayout?.portraitTop).toBeGreaterThanOrEqual(confirmationLayout?.confirmationTop ?? 0);
  expect(confirmationLayout?.portraitBottom).toBeLessThanOrEqual(confirmationLayout?.confirmationBottom ?? 0);
  await page.screenshot({path:testInfo.outputPath("draft-confirmation-mobile.png")});
  expect(await page.getByTestId("pick-context-strip").evaluate((e)=>e.getBoundingClientRect().height)).toBe(height);
  await expect(page.getByTestId("pick-confirmation")).toHaveCount(0,{timeout:4000});
  expect(state.submissions()).toBe(1);
  await page.reload();
  await expect(page.getByTestId("pick-context-strip")).toContainText("Last pick");
  await expect(page.getByTestId("pick-confirmation")).toHaveCount(0);
});

test("desktop inline timer stays clear of the fixed last-pick header and confirmation", async ({ page }) => {
  await fixture(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/league/77/draft");

  await page.getByRole("button", { name: "Draft Arch Manning", exact: true }).click();
  await expect(page.getByTestId("pick-confirmation")).toHaveAttribute("data-phase", "hold");

  const layout = await page.evaluate(() => {
    const timer = document.querySelector<HTMLElement>("[data-testid='real-draft-room-timer']");
    const header = document.querySelector<HTMLElement>("[data-testid='pick-context-strip']");
    const confirmation = document.querySelector<HTMLElement>("[data-testid='pick-confirmation']");
    const thumbnail = confirmation?.querySelector<HTMLElement>("[aria-hidden='true']");
    if (!timer || !header || !confirmation || !thumbnail) return null;

    return {
      timerPosition: getComputedStyle(timer).position,
      timerTop: timer.getBoundingClientRect().top,
      timerLeft: timer.getBoundingClientRect().left,
      timerRight: timer.getBoundingClientRect().right,
      timerBottom: timer.getBoundingClientRect().bottom,
      headerBottom: header.getBoundingClientRect().bottom,
      confirmationBottom: confirmation.getBoundingClientRect().bottom,
      thumbnailBottom: thumbnail.getBoundingClientRect().bottom,
      confirmationTop: confirmation.getBoundingClientRect().top,
      confirmationLeft: confirmation.getBoundingClientRect().left,
      confirmationRight: confirmation.getBoundingClientRect().right,
    };
  });

  expect(layout).not.toBeNull();
  expect(layout?.timerPosition).toBe("static");
  expect(layout?.timerTop).toBeGreaterThanOrEqual((layout?.headerBottom ?? 0) + 16);
  // The timer is now in the normal header flow. The confirmation may share
  // its vertical band but must never cover it or its clock text.
  expect(
    (layout?.timerTop ?? 0) >= (layout?.confirmationBottom ?? 0) ||
    (layout?.timerBottom ?? 0) <= (layout?.confirmationTop ?? 0) ||
    (layout?.timerLeft ?? 0) >= (layout?.confirmationRight ?? 0) ||
    (layout?.timerRight ?? 0) <= (layout?.confirmationLeft ?? 0)
  ).toBeTruthy();
});

test("poll failure retains board, disables picks and recovers; conflicts never celebrate", async ({ page }) => {
  const state = await fixture(page);
  await page.goto("/league/77/draft");
  await expect(page.getByRole("button",{name:"Draft Arch Manning",exact:true})).toBeEnabled();
  state.setFailure(true);
  await expect(page.getByText(/Reconnecting · Showing last confirmed/)).toBeVisible({timeout:12000});
  await expect(page.getByTestId("draft-player-row").filter({hasText:"Arch Manning"})).toBeVisible();
  await expect(page.getByRole("button",{name:"Draft Arch Manning",exact:true})).toBeDisabled();
  state.setFailure(false);
  await page.getByRole("button",{name:"Retry",exact:true}).click();
  await expect(page.getByRole("button",{name:"Draft Arch Manning",exact:true})).toBeEnabled({timeout:12000});
  state.reject();
  await page.getByRole("button",{name:"Draft Arch Manning",exact:true}).click();
  await expect(page.getByText(/Pick expired; waiting/)).toBeVisible();
  expect(state.submissions()).toBe(1);
  await expect(page.getByTestId("pick-confirmation")).toHaveCount(0);
});

test("final pick clears clock immediately and finishes banner before accessible completion", async ({ page }, testInfo) => {
  const state = await fixture(page);
  state.finishOnPick();
  await page.setViewportSize({width:390,height:844});
  await page.goto("/league/77/draft");
  await page.getByRole("button",{name:"Draft Arch Manning",exact:true}).click();
  await expect(page.getByTestId("pick-confirmation")).toBeVisible();
  await expect(page.getByText("Timer",{exact:true})).toHaveCount(0);
  await expect(page.getByRole("dialog")).toHaveCount(0);
  const dialog = page.getByRole("dialog",{name:"Draft Complete",exact:true});
  await expect(dialog).toBeVisible({timeout:5000});
  await expect(page.getByTestId("pick-confirmation")).toHaveCount(0);
  await expect(dialog.getByRole("button",{name:"View Your Roster",exact:true})).toBeFocused();
  await page.screenshot({path:testInfo.outputPath("draft-completion-mobile.png")});
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(page.getByTestId("draft-room-tabs").getByRole("button",{name:"Players",exact:true})).toBeFocused();
});
