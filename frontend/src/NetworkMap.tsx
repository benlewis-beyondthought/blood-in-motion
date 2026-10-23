import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { LocateFixedIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import type { State, Mission } from "./types";
import { names } from "./types";

export function NetworkMap({ state }: { state: State }) {
  const host = useRef<HTMLDivElement>(null),
    map = useRef<L.Map | null>(null),
    layers = useRef<L.LayerGroup | null>(null),
    latest = useRef(state);
  const [tileError, setTileError] = useState(false);
  latest.current = state;
  const fit = () => {
    const s = latest.current;
    map.current?.fitBounds(
      s.sites.map((x) => [Number(x.lat), Number(x.lon)] as L.LatLngTuple),
      { padding: [48, 48], maxZoom: 12, animate: false },
    );
  };
  useEffect(() => {
    if (!host.current) return;
    const m = L.map(host.current, {
      zoomControl: false,
      scrollWheelZoom: false,
      attributionControl: true,
    });
    map.current = m;
    L.control.zoom({ position: "bottomright" }).addTo(m);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    })
      .on("tileerror", () => setTileError(true))
      .addTo(m);
    layers.current = L.layerGroup().addTo(m);
    fit();
    const resize = new ResizeObserver(() => {
      m.invalidateSize();
      fit();
    });
    resize.observe(host.current);
    return () => {
      resize.disconnect();
      m.remove();
      map.current = null;
      layers.current = null;
    };
  }, []);
  useEffect(() => {
    const layer = layers.current;
    if (!layer) return;
    layer.clearLayers();
    const pos = (id: string): L.LatLngTuple => {
      const s = state.sites.find((x) => x.site_id === id);
      return s ? [Number(s.lat), Number(s.lon)] : [48.86, 2.34];
    };
    const lerp = (
      a: L.LatLngTuple,
      b: L.LatLngTuple,
      t: number,
    ): L.LatLngTuple => {
      const n = Math.max(0, Math.min(1, t));
      return [a[0] + (b[0] - a[0]) * n, a[1] + (b[1] - a[1]) * n];
    };
    const flight = (m: Mission) => {
      const start = Date.parse(m.reserved_at) / 1000,
        load = Date.parse(m.load_at) / 1000,
        depart = Date.parse(m.depart_at) / 1000,
        land = Date.parse(m.land_at) / 1000;
      if (state.timestamp < load)
        return lerp(
          pos(m.drone_start_site),
          pos(m.from_site_id),
          (state.timestamp - start) / (load - start || 1),
        );
      if (state.timestamp < depart) return pos(m.from_site_id);
      return lerp(
        pos(m.from_site_id),
        pos(m.to_site_id),
        (state.timestamp - depart) / (land - depart || 1),
      );
    };
    for (const s of state.sites) {
      const label = document.createElement("span");
      label.textContent = `${s.site_id} · ${names[s.site_id] || s.site_id}`;
      const marker = L.circleMarker(pos(s.site_id), {
        radius: s.site_type === "blood_bank" ? 9 : 7,
        weight: 3,
        color: "var(--map-node-ring)",
        fillColor:
          s.site_type === "blood_bank" ? "var(--map-bank)" : "var(--primary)",
        fillOpacity: 1,
      }).addTo(layer);
      marker.bindTooltip(label, {
        permanent: true,
        direction: s.site_id === "H2" ? "bottom" : "top",
        offset: [0, -8],
        className: "facility-label",
      });
      const popup = document.createElement("div");
      const title = document.createElement("strong");
      title.textContent = names[s.site_id] || s.site_id;
      popup.append(title);
      for (const [group, stock] of Object.entries(s.stock)) {
        const row = document.createElement("div");
        row.textContent = `${group}: ${stock.available} available · ${stock.reserved} reserved`;
        popup.append(row);
      }
      marker.bindPopup(popup);
    }
    for (const [a, b] of state.blocked_routes)
      L.polyline([pos(a), pos(b)], {
        color: "var(--destructive)",
        weight: 2,
        dashArray: "4 8",
      }).addTo(layer);
    state.drones.forEach((d, i) => {
      const mission = state.missions.find((m) => m.mission_id === d.mission_id);
      let p = pos(d.site_id);
      if (mission) {
        p = flight(mission);
        L.polyline(
          [
            pos(mission.drone_start_site),
            pos(mission.from_site_id),
            pos(mission.to_site_id),
          ],
          {
            color: "var(--map-route)",
            weight: 2,
            dashArray: "6 6",
            opacity: 0.8,
          },
        ).addTo(layer);
      }
      const icon = document.createElement("div");
      icon.className = "drone-label";
      icon.textContent = d.drone_id;
      L.marker(p, {
        icon: L.divIcon({
          className: "drone-marker",
          html: icon,
          iconSize: [28, 28],
          iconAnchor: [i ? 4 : 24, 14],
        }),
        title: `${d.drone_id} · ${d.status}`,
        zIndexOffset: 500,
      }).addTo(layer);
    });
  }, [state]);
  return (
    <div className="network-map-wrap">
      <div
        ref={host}
        className="network-map"
        aria-label="Paris hospitals, blood banks and simulated drone routes"
      />
      <div className="map-toolbar">
        <Button
          variant="outline"
          size="icon"
          aria-label="Fit all locations"
          onClick={fit}
        >
          <LocateFixedIcon data-icon="inline-start" />
        </Button>
      </div>
      {tileError && (
        <Alert className="map-alert">
          <AlertDescription>
            Map tiles are unavailable. Facility locations and routes remain
            visible.
          </AlertDescription>
        </Alert>
      )}
    </div>
  );
}
