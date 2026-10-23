export type Site = {
  site_id: string;
  site_type: string;
  lat: number | string;
  lon: number | string;
  available: number;
  stock: Record<string, { available: number; reserved: number }>;
};
export type HospitalRequest = {
  request_id: string;
  site_id: string;
  blood_type: string;
  units: number;
  fulfilled: number;
  status: string;
  priority: string;
  deadline: string;
  waiting_reason?: string;
};
export type Drone = {
  drone_id: string;
  site_id: string;
  status: string;
  mission_id: string | null;
};
export type Plan = {
  plan_id: string;
  request_id: string;
  drone_id: string;
  from_site_id: string;
  to_site_id: string;
  units: number;
  blood_type: string;
  arrival_at: string;
  delivery_km: number;
  source_reserve: number;
  drone_start_site: string;
};
export type Mission = Plan & {
  mission_id: string;
  status: string;
  reserved_at: string;
  load_at: string;
  depart_at: string;
  land_at: string;
};
export type Projection = {
  request_id: string;
  drone_id: string;
  source: string;
  destination: string;
  projected_fulfilled: number[];
  projected_flight_km: number;
};
export type Planning = {
  as_of: string;
  horizon_end: string;
  selected: Projection;
  baseline: Projection;
  alternatives: Projection[];
  objective: string;
};
export type Diagnostic = {
  request_id: string;
  site_id: string;
  blood_type: string;
  as_of: string;
  uncommitted_units: number;
  committed_units: number;
  flags: string[];
  sources: {
    site_id: string;
    available: number;
    reserve: number;
    releasable: number;
  }[];
};
export type Experiment = {
  request_id: string;
  as_of: string;
  until: string;
  method: string;
  limitation: string;
  results: {
    id: string;
    label: string;
    fulfilled: number;
    unmet: number;
    additional_units: number;
    system_delta: number[];
  }[];
};
export type State = {
  clock: string;
  timestamp: number;
  mode: string;
  scheduler?: string;
  finished: boolean;
  version: number;
  stats: {
    available: number;
    reserved: number;
    in_transit: number;
    fulfilled: number;
    requested: number;
    unmet_at_deadline: number;
    api_calls: number;
    api_successes: number;
    fallbacks: number;
    conservation: string;
  };
  sites: Site[];
  drones: Drone[];
  missions: Mission[];
  requests: HospitalRequest[];
  drone_config: { payload_units: number };
  blocked_routes: [string, string][];
  social: {
    report_id: string;
    text: string;
    available_at: string;
    flag: string;
    evidence: string;
    origin: string;
    policy_adjusted?: boolean;
    model_flag?: string;
  }[];
  decisions: {
    request_id: string;
    origin: string;
    reason: string;
    receipt_id?: string;
    selected_plan_id: string;
    candidates: Plan[];
    planning?: Planning;
  }[];
  planning?: Planning | null;
  diagnostics?: Diagnostic[];
  experiments?: Record<string, Experiment>;
  log: { at: string; kind: string; message: string }[];
};
export type Replay = { schema: string; frames: State[] };
export const names: Record<string, string> = {
  H1: "Lariboisière",
  H2: "Pitié-Salpêtrière",
  H3: "Georges-Pompidou",
  H4: "Bichat",
  B1: "Crozatier",
  B2: "Cabanel",
};
export const groups = ["O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-"];
export const time = (t: string) =>
  new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/Paris",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(t));
export const number = (n: number) => n.toLocaleString("en-GB");
