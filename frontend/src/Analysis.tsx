import { useState } from "react";
import {
  ArrowRightIcon,
  FlaskConicalIcon,
  InfoIcon,
  ListFilterIcon,
  RouteIcon,
} from "lucide-react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
  CardAction,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  NativeSelect,
  NativeSelectOption,
} from "@/components/ui/native-select";
import { Field, FieldLabel } from "@/components/ui/field";
import {
  Dialog,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  Table,
  TableHeader,
  TableRow,
  TableHead,
  TableBody,
  TableCell,
} from "@/components/ui/table";
import {
  Empty,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
  EmptyDescription,
} from "@/components/ui/empty";
import type { State } from "./types";
import { names, time } from "./types";

const flags: Record<string, string> = {
  INSUFFICIENT_AVAILABLE_GROUP: "Insufficient available stock",
  STOCK_PROTECTED_BY_RESERVE: "Protected reserves",
  ALL_DRONES_BUSY: "Fleet occupied",
  ROUTE_RESTRICTION: "Restricted route",
  DEADLINE_OR_MISSION_LIMIT: "Time limit",
  NO_IMMEDIATE_FEASIBLE_DISPATCH: "No immediate dispatch",
  FEASIBLE_BUT_COMPETING_FOR_FLEET: "Competing requests",
};
export function Analysis({
  state,
  busy,
  recorded,
  compare,
}: {
  state: State;
  busy: boolean;
  recorded: boolean;
  compare: (id: string) => void;
}) {
  const [chosen, setChosen] = useState("");
  const diagnostics = state.diagnostics || [],
    d = diagnostics.find((d) => d.request_id === chosen) || diagnostics[0];
  const experiment = d ? state.experiments?.[d.request_id] : undefined,
    p = state.planning,
    last = state.decisions.at(-1);
  return (
    <div className="analysis-grid">
      <Card>
        <CardHeader>
          <CardTitle>Why this plan?</CardTitle>
          <CardDescription>
            The reasoning behind the latest dispatch.
          </CardDescription>
          <CardAction>
            <Badge variant="outline">
              {state.scheduler === "rolling"
                ? "90-min lookahead"
                : "Individual transfer"}
            </Badge>
          </CardAction>
        </CardHeader>
        <CardContent className="flex flex-col gap-5">
          {p ? (
            <>
              <div className="selected-route">
                <div className="route-location">
                  <span className="eyebrow">FROM</span>
                  <strong>{names[p.selected.source]}</strong>
                  <span>{p.selected.source}</span>
                </div>
                <ArrowRightIcon />
                <div className="route-location">
                  <span className="eyebrow">TO</span>
                  <strong>{names[p.selected.destination]}</strong>
                  <span>{p.selected.destination}</span>
                </div>
                <Badge variant="secondary">{p.selected.drone_id}</Badge>
              </div>
              <p className="supporting-copy">
                {p.alternatives.length} initial actions tested at{" "}
                {time(p.as_of)}, looking ahead to {time(p.horizon_end)}.
              </p>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Projected units delivered</TableHead>
                    <TableHead>Chosen</TableHead>
                    <TableHead>Greedy</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {["Critical", "Scheduled", "Routine"].map((label, i) => (
                    <TableRow key={label}>
                      <TableCell>{label}</TableCell>
                      <TableCell>{p.selected.projected_fulfilled[i]}</TableCell>
                      <TableCell>{p.baseline.projected_fulfilled[i]}</TableCell>
                    </TableRow>
                  ))}
                  <TableRow>
                    <TableCell>Flight distance</TableCell>
                    <TableCell>
                      {p.selected.projected_flight_km.toFixed(1)} km
                    </TableCell>
                    <TableCell>
                      {p.baseline.projected_flight_km.toFixed(1)} km
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>
              <Dialog>
                <DialogTrigger render={<Button variant="outline" />}>
                  <ListFilterIcon data-icon="inline-start" />
                  Inspect alternatives
                </DialogTrigger>
                <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-2xl">
                  <DialogHeader>
                    <DialogTitle>Tested dispatches</DialogTitle>
                    <DialogDescription>
                      {p.objective}. Each first action is followed by a greedy
                      continuation.
                    </DialogDescription>
                  </DialogHeader>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Request / route</TableHead>
                        <TableHead>Drone</TableHead>
                        <TableHead>Critical / scheduled / routine</TableHead>
                        <TableHead>Distance</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {p.alternatives.map((a, i) => (
                        <TableRow key={i}>
                          <TableCell>
                            {a.request_id}
                            <br />
                            {a.source} → {a.destination}
                          </TableCell>
                          <TableCell>{a.drone_id}</TableCell>
                          <TableCell>
                            {a.projected_fulfilled.join(" / ")}
                          </TableCell>
                          <TableCell>
                            {a.projected_flight_km.toFixed(1)} km
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </DialogContent>
              </Dialog>
            </>
          ) : last ? (
            <>
              <Badge variant="secondary">
                {last.origin.replaceAll("_", " ")}
              </Badge>
              <p className="supporting-copy">{last.reason}</p>
              {last.candidates.map((c) => (
                <div className="dispatch-option" key={c.plan_id}>
                  <span>
                    {c.from_site_id} → {c.to_site_id} · {c.units} {c.blood_type}
                  </span>
                  <Badge
                    variant={
                      c.plan_id === last.selected_plan_id
                        ? "default"
                        : "outline"
                    }
                  >
                    {c.plan_id === last.selected_plan_id
                      ? "Selected"
                      : c.drone_id}
                  </Badge>
                </div>
              ))}
              {last.receipt_id && (
                <p className="supporting-copy">API receipt {last.receipt_id}</p>
              )}
            </>
          ) : (
            <Empty>
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <RouteIcon />
                </EmptyMedia>
                <EmptyTitle>Ready to find a route</EmptyTitle>
                <EmptyDescription>
                  Send a request or advance the simulation to see a transfer
                  decision.
                </EmptyDescription>
              </EmptyHeader>
            </Empty>
          )}
        </CardContent>
        <CardFooter>
          <p className="fine-print">
            Only known requests and published activity are considered. Bounded
            search, not a proven global optimum.
          </p>
        </CardFooter>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>What would help?</CardTitle>
          <CardDescription>
            Understand a shortage. Test a possible response.
          </CardDescription>
          <CardAction>
            <Badge variant="secondary">What-if</Badge>
          </CardAction>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {!d ? (
            <Empty>
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <FlaskConicalIcon />
                </EmptyMedia>
                <EmptyTitle>No unresolved shortages</EmptyTitle>
                <EmptyDescription>
                  When a request cannot be fully assigned, investigate it here.
                </EmptyDescription>
              </EmptyHeader>
            </Empty>
          ) : (
            <>
              <Field>
                <FieldLabel htmlFor="shortage-select">
                  Request to investigate
                </FieldLabel>
                <NativeSelect
                  id="shortage-select"
                  className="w-full"
                  value={d.request_id}
                  onChange={(e) => setChosen(e.target.value)}
                >
                  {diagnostics.map((x) => (
                    <NativeSelectOption key={x.request_id} value={x.request_id}>
                      {x.request_id} · {names[x.site_id]} · {x.blood_type}
                    </NativeSelectOption>
                  ))}
                </NativeSelect>
              </Field>
              <div className="shortage-summary">
                <strong>
                  {d.uncommitted_units}
                  <span> units uncommitted</span>
                </strong>
                <p>
                  {d.committed_units} assigned to deliveries · observed{" "}
                  {time(d.as_of)}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                {d.flags.map((flag) => (
                  <Badge variant="outline" key={flag}>
                    {flags[flag] || flag}
                  </Badge>
                ))}
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="secondary"
                  onClick={() => compare(d.request_id)}
                  disabled={busy || recorded}
                >
                  <FlaskConicalIcon data-icon="inline-start" />
                  {busy ? "Comparing…" : "Compare interventions"}
                </Button>
                <Dialog>
                  <DialogTrigger
                    render={
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label="Inspect shortage constraints"
                      />
                    }
                  >
                    <InfoIcon data-icon="inline-start" />
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>Shortage constraints</DialogTitle>
                      <DialogDescription>
                        Observed constraints can overlap. They do not prove a
                        single cause.
                      </DialogDescription>
                    </DialogHeader>
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Donor</TableHead>
                          <TableHead>Available</TableHead>
                          <TableHead>Reserve</TableHead>
                          <TableHead>Releasable</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {d.sources.map((source) => (
                          <TableRow key={source.site_id}>
                            <TableCell>{source.site_id}</TableCell>
                            <TableCell>{source.available}</TableCell>
                            <TableCell>{source.reserve}</TableCell>
                            <TableCell>{source.releasable}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                    <p className="fine-print">
                      Releasable stock must still pass route, expiry and arrival
                      checks.
                    </p>
                  </DialogContent>
                </Dialog>
              </div>
              {experiment && (
                <div className="experiment-results" aria-live="polite">
                  <p className="eyebrow">PROJECTED AT THE ORIGINAL DEADLINE</p>
                  {experiment.results.map((r) => (
                    <div className="experiment-row" key={r.id}>
                      <div>
                        <strong>{r.label}</strong>
                        <p>
                          {r.fulfilled} fulfilled · {r.unmet} unmet
                        </p>
                        {r.id !== "baseline" && (
                          <small>
                            System Δ {r.system_delta.join(" / ")} critical /
                            scheduled / routine
                          </small>
                        )}
                      </div>
                      <Badge
                        variant={
                          r.additional_units > 0 ? "default" : "secondary"
                        }
                      >
                        {r.additional_units >= 0 ? "+" : ""}
                        {r.additional_units} units
                      </Badge>
                    </div>
                  ))}
                  <p className="fine-print">
                    From the first unresolved snapshot at{" "}
                    {time(experiment.as_of)}. Isolated greedy continuations;
                    later unknown events are excluded.
                  </p>
                </div>
              )}
            </>
          )}
        </CardContent>
        <CardFooter>
          <p className="fine-print">
            Hypothetical changes only. Live inventory and drone assignments stay
            unchanged.
          </p>
        </CardFooter>
      </Card>
    </div>
  );
}
