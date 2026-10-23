import { useRef, useState } from "react";
import {
  ActivityIcon,
  ArrowDownToLineIcon,
  ArrowRightIcon,
  CheckIcon,
  ChevronDownIcon,
  Clock3Icon,
  DropletIcon,
  DroneIcon,
  FileUpIcon,
  HistoryIcon,
  InboxIcon,
  MapPinIcon,
  PauseIcon,
  PlayIcon,
  PlusIcon,
  RotateCcwIcon,
  ShieldCheckIcon,
  SkipForwardIcon,
  RadioIcon,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardAction,
  CardContent,
  CardFooter,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogTrigger,
  DialogClose,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { FieldGroup, Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  NativeSelect,
  NativeSelectOption,
} from "@/components/ui/native-select";
import { Separator } from "@/components/ui/separator";
import { Slider } from "@/components/ui/slider";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Empty,
  EmptyHeader,
  EmptyTitle,
  EmptyDescription,
  EmptyMedia,
} from "@/components/ui/empty";
import {
  Table,
  TableHeader,
  TableRow,
  TableHead,
  TableCell,
  TableBody,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { useSimulation } from "./use-simulation";
import { NetworkMap } from "./NetworkMap";
import { Analysis } from "./Analysis";
import { groups, names, number, time } from "./types";

export default function App() {
  const sim = useSimulation(),
    s = sim.state,
    file = useRef<HTMLInputElement>(null);
  const [requestOpen, setRequestOpen] = useState(false),
    [priority, setPriority] = useState("critical"),
    [detailTab, setDetailTab] = useState("analysis");
  const recorded = Boolean(sim.replay);
  if (!s)
    return (
      <div className="loading-shell">
        <div className="brand">
          <DropletIcon />
          Blood in motion
        </div>
        {sim.error ? (
          <Alert variant="destructive">
            <AlertTitle>Cannot connect</AlertTitle>
            <AlertDescription>{sim.error}</AlertDescription>
          </Alert>
        ) : (
          <>
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-96 w-full" />
          </>
        )}
      </div>
    );
  const waiting = s.requests.filter((r) => r.status === "waiting"),
    moving = s.stats.reserved + s.stats.in_transit;
  const controller =
    s.scheduler === "rolling"
      ? "Rolling horizon"
      : s.mode === "decisions_live"
        ? "Decisions API"
        : "Greedy baseline";
  const statusOrder: Record<string, number> = {
    waiting: 0,
    missed: 1,
    fulfilled: 2,
  };
  const requests = [...s.requests].sort(
    (a, b) =>
      (statusOrder[a.status] ?? 3) - (statusOrder[b.status] ?? 3) ||
      (a.status === "waiting"
        ? ["critical", "scheduled", "routine"].indexOf(a.priority) -
            ["critical", "scheduled", "routine"].indexOf(b.priority) ||
          Date.parse(a.deadline) - Date.parse(b.deadline)
        : 0) ||
      b.request_id.localeCompare(a.request_id, undefined, { numeric: true }),
  );
  const date = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/Paris",
    weekday: "short",
    day: "numeric",
    month: "short",
  }).format(new Date(s.clock));
  const clock = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/Paris",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    timeZoneName: "short",
  }).format(new Date(s.clock));
  const openRequest = () => {
    sim.setPlaying(false);
    setRequestOpen(true);
  };
  return (
    <>
      <a className="skip-link" href="#main">
        Skip to simulation
      </a>
      <header className="app-header">
        <div className="header-inner">
          <div className="brand">
            <span className="brand-mark">
              <DropletIcon />
            </span>
            <span>
              Blood in motion
              <span className="brand-subtitle">Paris response network</span>
            </span>
          </div>
          <div className="header-meta">
            <Badge variant="outline">
              <span className="status-dot" />
              Synthetic simulation
            </Badge>
            <span className="header-region">
              <MapPinIcon />
              Paris, France
            </span>
          </div>
        </div>
      </header>
      <main id="main" className="app-shell">
        <section className="page-heading">
          <div>
            <p className="eyebrow">OPERATIONS / PARIS</p>
            <h1>
              The right blood.
              <br className="mobile-break" /> In the right place.
            </h1>
            <p className="page-description">
              A connected view of supply, demand and the routes between them.
            </p>
          </div>
          <div className="simulation-clock">
            <span>{date} · 2026</span>
            <strong>{clock}</strong>
            <Badge variant="secondary">
              {recorded ? "Recorded replay" : controller}
            </Badge>
          </div>
        </section>
        <div className="control-bar">
          <div className="playback-controls">
            <Button
              size="lg"
              onClick={() => sim.setPlaying(!sim.playing)}
              disabled={sim.ended}
            >
              {sim.playing ? (
                <PauseIcon data-icon="inline-start" />
              ) : (
                <PlayIcon data-icon="inline-start" />
              )}
              {sim.playing ? "Pause" : "Play simulation"}
            </Button>
            <Button
              size="lg"
              variant="outline"
              onClick={sim.step}
              disabled={sim.busy || sim.ended}
            >
              <SkipForwardIcon data-icon="inline-start" />
              Next event
            </Button>
            <Separator orientation="vertical" className="control-divider h-6" />
            <ToggleGroup
              aria-label="Playback speed"
              size="sm"
              value={[sim.speed]}
              onValueChange={(v) => {
                if (v[0]) sim.setSpeed(v[0]);
              }}
              spacing={0}
            >
              {[
                ["800", "1×"],
                ["300", "3×"],
                ["80", "10×"],
              ].map(([value, label]) => (
                <ToggleGroupItem
                  key={value}
                  value={value}
                  aria-label={`${label} speed`}
                >
                  {label}
                </ToggleGroupItem>
              ))}
            </ToggleGroup>
          </div>
          <div className="secondary-controls">
            <DropdownMenu>
              <DropdownMenuTrigger
                render={<Button variant="ghost" size="lg" />}
              >
                Replay & tools
                <ChevronDownIcon data-icon="inline-end" />
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-52">
                <DropdownMenuGroup>
                  <DropdownMenuItem
                    disabled={sim.busy}
                    onClick={() => void sim.review()}
                  >
                    <HistoryIcon />
                    Review this run
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    disabled={sim.busy}
                    onClick={() => file.current?.click()}
                  >
                    <FileUpIcon />
                    Open saved replay
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    render={
                      <a
                        href="/api/export"
                        download="paris-drone-replay.json"
                      />
                    }
                  >
                    <ArrowDownToLineIcon />
                    Save live replay
                  </DropdownMenuItem>
                </DropdownMenuGroup>
                <DropdownMenuSeparator />
                <DropdownMenuGroup>
                  <DropdownMenuItem
                    disabled={sim.busy || recorded}
                    onClick={() => {
                      sim.setPlaying(false);
                      void sim.action("/api/restart");
                    }}
                  >
                    <RotateCcwIcon />
                    New run
                  </DropdownMenuItem>
                </DropdownMenuGroup>
              </DropdownMenuContent>
            </DropdownMenu>
            <Button
              variant="outline"
              size="lg"
              disabled={sim.busy || recorded || s.finished}
              onClick={openRequest}
            >
              <PlusIcon data-icon="inline-start" />
              New request
            </Button>
          </div>
        </div>
        <input
          ref={file}
          type="file"
          accept=".json,application/json"
          className="sr-only"
          aria-label="Open saved replay file"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) void sim.importReplay(f);
            e.target.value = "";
          }}
        />
        {recorded && (
          <div className="replay-bar">
            <Badge variant="outline">Replay</Badge>
            <Slider
              aria-label="Recorded event"
              value={[sim.index]}
              min={0}
              max={Math.max(1, sim.replay!.frames.length - 1)}
              disabled={sim.replay!.frames.length < 2}
              onValueChange={(value) =>
                sim.seek(Array.isArray(value) ? value[0] : value)
              }
              className="flex-1"
            />
            <span>
              {sim.index + 1} / {sim.replay!.frames.length}
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => void sim.returnLive()}
            >
              Return to live
              <ArrowRightIcon data-icon="inline-end" />
            </Button>
          </div>
        )}
        <div className="operation-status" role="status">
          {sim.busy ? (
            <>
              <ActivityIcon />
              Evaluating the next action…
            </>
          ) : recorded ? (
            "Recorded responses. No new API calls."
          ) : s.finished ? (
            "Weekend complete. Review this run or start again."
          ) : sim.playing ? (
            "Simulation running. The clock pauses while decisions are evaluated."
          ) : (
            "Simulation paused. Advance an event or add a hospital request."
          )}
        </div>
        {sim.error && (
          <Alert variant="destructive">
            <AlertTitle>Action could not be completed</AlertTitle>
            <AlertDescription>{sim.error}</AlertDescription>
          </Alert>
        )}
        <section className="metrics" aria-label="Network totals">
          {[
            {
              label: "Available stock",
              value: number(s.stats.available),
              detail: "units across the network",
              icon: DropletIcon,
            },
            {
              label: "In transit & reserved",
              value: number(moving),
              detail: `${s.drones.filter((d) => d.status !== "idle").length} of ${s.drones.length} drones assigned`,
              icon: DroneIcon,
            },
            {
              label: "Demand fulfilled",
              value: number(s.stats.fulfilled),
              detail: `of ${number(s.stats.requested)} requested units`,
              icon: CheckIcon,
            },
            {
              label: "Unmet at deadline",
              value: number(s.stats.unmet_at_deadline),
              detail: "units still needed",
              icon: Clock3Icon,
            },
          ].map((m, i) => (
            <div
              key={m.label}
              className={cn(
                "metric",
                i === 3 && s.stats.unmet_at_deadline > 0 && "metric-alert",
              )}
            >
              <div className="metric-label">
                <span>{m.label}</span>
                <m.icon />
              </div>
              <strong>{m.value}</strong>
              <span className="metric-detail">{m.detail}</span>
            </div>
          ))}
        </section>
        <div className="operations-grid">
          <Card className="map-card">
            <CardHeader>
              <CardTitle>Distribution network</CardTitle>
              <CardDescription>
                {s.sites.length} locations · {s.drones.length} simulated drones
              </CardDescription>
              <CardAction>
                <div className="map-legend">
                  <span>
                    <i className="legend-hospital" />
                    Hospital
                  </span>
                  <span>
                    <i className="legend-bank" />
                    Bank
                  </span>
                </div>
              </CardAction>
            </CardHeader>
            <CardContent className="px-0">
              <NetworkMap state={s} />
            </CardContent>
            <CardFooter className="fleet-footer">
              {s.drones.map((d) => {
                const mission = s.missions.find(
                  (m) => m.mission_id === d.mission_id,
                );
                return (
                  <div className="fleet-item" key={d.drone_id}>
                    <span className="fleet-icon">
                      <DroneIcon />
                    </span>
                    <div>
                      <div className="fleet-title">
                        <strong>{d.drone_id}</strong>
                        <Badge variant="outline">{d.status}</Badge>
                      </div>
                      <p>
                        {mission
                          ? `${mission.units} ${mission.blood_type} · ${mission.from_site_id} → ${mission.to_site_id}`
                          : `Ready at ${names[d.site_id]}`}
                      </p>
                      {mission && (
                        <small>
                          Available at destination {time(mission.arrival_at)}
                        </small>
                      )}
                    </div>
                  </div>
                );
              })}
            </CardFooter>
          </Card>
          <Card className="feed-card">
            <CardHeader>
              <CardTitle>Incoming activity</CardTitle>
              <CardDescription>
                Requests and reports as they arrive.
              </CardDescription>
              <CardAction>
                <Badge variant="secondary">{waiting.length} waiting</Badge>
              </CardAction>
            </CardHeader>
            <CardContent className="flex-1">
              <Tabs defaultValue="requests">
                <TabsList className="w-full">
                  <TabsTrigger value="requests">
                    Requests{" "}
                    <span className="tab-count">{s.requests.length}</span>
                  </TabsTrigger>
                  <TabsTrigger value="social">
                    Social <span className="tab-count">{s.social.length}</span>
                  </TabsTrigger>
                </TabsList>
                <TabsContent value="requests">
                  <div className="activity-list">
                    {!requests.length ? (
                      <Empty>
                        <EmptyHeader>
                          <EmptyMedia variant="icon">
                            <InboxIcon />
                          </EmptyMedia>
                          <EmptyTitle>Ready for the first request</EmptyTitle>
                          <EmptyDescription>
                            Add a request or play the simulation.
                          </EmptyDescription>
                        </EmptyHeader>
                      </Empty>
                    ) : (
                      requests.map((r) => (
                        <div className="request-row" key={r.request_id}>
                          <div className="request-row-top">
                            <span className="blood-tag">{r.blood_type}</span>
                            <div className="request-location">
                              <strong>{names[r.site_id]}</strong>
                              <span>
                                {r.request_id} · {r.priority}
                              </span>
                            </div>
                            <Badge
                              variant={
                                r.status === "missed"
                                  ? "destructive"
                                  : r.status === "fulfilled"
                                    ? "secondary"
                                    : "outline"
                              }
                            >
                              {r.status === "missed"
                                ? "Shortfall"
                                : r.status === "fulfilled"
                                  ? "Fulfilled"
                                  : "Waiting"}
                            </Badge>
                          </div>
                          <div className="request-row-bottom">
                            <span>
                              <strong>{r.fulfilled}</strong> / {r.units} units
                            </span>
                            <span>Due {time(r.deadline)}</span>
                          </div>
                          <progress
                            value={r.fulfilled}
                            max={r.units}
                            aria-label={`${r.request_id} fulfilment`}
                          />
                        </div>
                      ))
                    )}
                  </div>
                </TabsContent>
                <TabsContent value="social">
                  <div className="activity-list">
                    {!s.social.length ? (
                      <Empty>
                        <EmptyHeader>
                          <EmptyMedia variant="icon">
                            <RadioIcon />
                          </EmptyMedia>
                          <EmptyTitle>No reports yet</EmptyTitle>
                          <EmptyDescription>
                            Social evidence will appear as the weekend unfolds.
                          </EmptyDescription>
                        </EmptyHeader>
                      </Empty>
                    ) : (
                      [...s.social].reverse().map((r) => (
                        <div className="social-row" key={r.report_id}>
                          <div className="social-row-top">
                            <span>
                              {r.report_id} · {time(r.available_at)}
                            </span>
                            <Badge
                              variant={
                                r.flag === "URGENT_REVIEW"
                                  ? "destructive"
                                  : "outline"
                              }
                            >
                              {r.flag.replaceAll("_", " ")}
                            </Badge>
                          </div>
                          <p>{r.text}</p>
                          <small>
                            {r.evidence.replaceAll("_", " ")} ·{" "}
                            {r.origin.replaceAll("_", " ")}
                            {r.policy_adjusted &&
                              ` · adjusted from ${r.model_flag}`}
                          </small>
                        </div>
                      ))
                    )}
                  </div>
                </TabsContent>
              </Tabs>
            </CardContent>
            <CardFooter>
              <p className="fine-print">
                Social reports trigger review. Hospital requests specify blood
                demand.
              </p>
            </CardFooter>
          </Card>
        </div>
        <section className="details-section">
          <Tabs
            value={detailTab}
            onValueChange={(v) => setDetailTab(String(v))}
          >
            <div className="details-heading">
              <TabsList variant="line">
                <TabsTrigger value="analysis">Decision insights</TabsTrigger>
                <TabsTrigger value="stock">Inventory</TabsTrigger>
                <TabsTrigger value="log">Event log</TabsTrigger>
              </TabsList>
              <span className="ledger-status">
                <ShieldCheckIcon />
                {s.stats.conservation === "PASS"
                  ? "Inventory reconciled"
                  : "Check inventory"}
              </span>
            </div>
            <TabsContent value="analysis">
              <Analysis
                state={s}
                busy={sim.busy}
                recorded={recorded}
                compare={(id) => {
                  sim.setPlaying(false);
                  void sim.action("/api/what-if", { request_id: id });
                }}
              />
            </TabsContent>
            <TabsContent value="stock">
              <Card>
                <CardHeader>
                  <CardTitle>Stock at each facility</CardTitle>
                  <CardDescription>
                    Available units by blood group. Reserved stock is tracked
                    separately.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Facility</TableHead>
                        {groups.map((g) => (
                          <TableHead key={g}>{g}</TableHead>
                        ))}
                        <TableHead>Reserved</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {s.sites.map((site) => (
                        <TableRow key={site.site_id}>
                          <TableCell>
                            {site.site_id} · {names[site.site_id]}
                          </TableCell>
                          {groups.map((g) => (
                            <TableCell key={g}>
                              <span
                                className={cn(
                                  site.stock[g].available === 0 && "stock-zero",
                                )}
                              >
                                {site.stock[g].available}
                              </span>
                            </TableCell>
                          ))}
                          <TableCell>
                            {Object.values(site.stock).reduce(
                              (n, c) => n + c.reserved,
                              0,
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </CardContent>
                <CardFooter>
                  <p className="fine-print">
                    Exact blood-group matching. Declared reserves and expiry
                    checks apply.
                  </p>
                </CardFooter>
              </Card>
            </TabsContent>
            <TabsContent value="log">
              <Card>
                <CardHeader>
                  <CardTitle>Event ledger</CardTitle>
                  <CardDescription>
                    {s.stats.api_successes} successful API calls ·{" "}
                    {s.stats.api_calls} attempts · {s.stats.fallbacks} fallbacks
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="event-log">
                    {[...s.log].reverse().map((entry, i) => (
                      <div className="event-row" key={i}>
                        <time>{time(entry.at)}</time>
                        <Badge variant="outline">{entry.kind}</Badge>
                        <span>{entry.message}</span>
                      </div>
                    ))}
                  </div>
                </CardContent>
                <CardFooter>
                  <p className="fine-print">
                    The latest operational events. Full history is preserved in
                    the replay.
                  </p>
                </CardFooter>
              </Card>
            </TabsContent>
          </Tabs>
        </section>
        <footer className="page-footer">
          <span>Paris · 23–25 October 2026</span>
          <Dialog>
            <DialogTrigger render={<Button variant="link" size="sm" />}>
              Simulation assumptions
            </DialogTrigger>
            <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-xl">
              <DialogHeader>
                <DialogTitle>A synthetic network</DialogTitle>
                <DialogDescription>
                  Built to explore emergency blood distribution. Clinical
                  allocation and drone transport are not validated.
                </DialogDescription>
              </DialogHeader>
              <div className="assumptions-copy">
                <p>
                  Two drones carry four packaged units each, fly at 60 km/h, and
                  spend two minutes loading and unloading. Missions use
                  straight-line geometry with a 40-minute limit. Real air
                  corridors, charging and cold-chain performance are not
                  modelled.
                </p>
                <p>
                  Banks retain one baseline day of stock. Donor hospitals retain
                  the larger of baseline, planned demand and waiting requests.
                  Planned activity arrives at 09:00 and residual baseline demand
                  at 15:00. External supplier routes are unsupported.
                </p>
                <p>
                  Lookahead uses current requests and published planned
                  activity. It does not see future scripted emergencies or
                  social reports. Existing flights continue after a route
                  closure; unlaunched deliveries are cancelled.
                </p>
                <p>
                  What-if comparisons are isolated projections. They make no API
                  calls and do not change live stock. Social evidence does not
                  directly create blood demand.
                </p>
                <p>
                  Map © OpenStreetMap contributors. Interface built with
                  shadcn/ui.
                </p>
              </div>
            </DialogContent>
          </Dialog>
        </footer>
      </main>
      <Dialog open={requestOpen} onOpenChange={setRequestOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>New hospital request</DialogTitle>
            <DialogDescription>
              Add confirmed demand to the synthetic network.
            </DialogDescription>
          </DialogHeader>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              const data = new FormData(e.currentTarget);
              const ok = await sim.action("/api/request", {
                site_id: data.get("site_id"),
                blood_type: data.get("blood_type"),
                units: Number(data.get("units")),
                deadline_minutes: Number(data.get("deadline_minutes")),
                priority,
              });
              if (ok) setRequestOpen(false);
            }}
          >
            <FieldGroup>
              <FieldGroup className="grid grid-cols-2 gap-4">
                <Field data-disabled={sim.busy}>
                  <FieldLabel htmlFor="hospital">Hospital</FieldLabel>
                  <NativeSelect
                    id="hospital"
                    name="site_id"
                    defaultValue="H1"
                    disabled={sim.busy}
                    className="w-full"
                  >
                    {s.sites
                      .filter((x) => x.site_type === "hospital")
                      .map((x) => (
                        <NativeSelectOption value={x.site_id} key={x.site_id}>
                          {names[x.site_id]}
                        </NativeSelectOption>
                      ))}
                  </NativeSelect>
                </Field>
                <Field data-disabled={sim.busy}>
                  <FieldLabel htmlFor="blood">Blood group</FieldLabel>
                  <NativeSelect
                    id="blood"
                    name="blood_type"
                    defaultValue="O-"
                    disabled={sim.busy}
                    className="w-full"
                  >
                    {groups.map((g) => (
                      <NativeSelectOption key={g}>{g}</NativeSelectOption>
                    ))}
                  </NativeSelect>
                </Field>
                <Field data-disabled={sim.busy}>
                  <FieldLabel htmlFor="units">Units needed</FieldLabel>
                  <Input
                    id="units"
                    name="units"
                    type="number"
                    min={1}
                    max={100}
                    defaultValue={8}
                    required
                    disabled={sim.busy}
                  />
                </Field>
                <Field data-disabled={sim.busy}>
                  <FieldLabel htmlFor="deadline">Due in (min)</FieldLabel>
                  <Input
                    id="deadline"
                    name="deadline_minutes"
                    type="number"
                    min={1}
                    max={180}
                    defaultValue={45}
                    required
                    disabled={sim.busy}
                  />
                </Field>
              </FieldGroup>
              <Field data-disabled={sim.busy}>
                <FieldLabel>Priority</FieldLabel>
                <ToggleGroup
                  aria-label="Request priority"
                  variant="outline"
                  value={[priority]}
                  onValueChange={(v) => {
                    if (v[0]) setPriority(v[0]);
                  }}
                  disabled={sim.busy}
                  spacing={0}
                  className="w-full"
                >
                  {["critical", "scheduled", "routine"].map((v) => (
                    <ToggleGroupItem className="flex-1" value={v} key={v}>
                      {v[0].toUpperCase() + v.slice(1)}
                    </ToggleGroupItem>
                  ))}
                </ToggleGroup>
              </Field>
              {sim.error && (
                <Alert variant="destructive">
                  <AlertDescription>{sim.error}</AlertDescription>
                </Alert>
              )}
            </FieldGroup>
            <DialogFooter className="mt-6">
              <DialogClose
                render={
                  <Button variant="outline" type="button" disabled={sim.busy} />
                }
              >
                Cancel
              </DialogClose>
              <Button type="submit" disabled={sim.busy}>
                {sim.busy ? "Finding a plan…" : "Send request"}
                <ArrowRightIcon data-icon="inline-end" />
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
