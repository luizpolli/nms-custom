{{- define "nms-custom.name" -}}nms-custom{{- end -}}
{{- define "nms-custom.labels" -}}
app.kubernetes.io/name: {{ include "nms-custom.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{/*
Pod anti-affinity block. Args: list of (component, root-context).
Produces a podAntiAffinity stanza that keeps replicas off the same node/zone.
*/}}
{{- define "nms-custom.podAntiAffinity" -}}
{{- $component := index . 0 -}}
{{- $root := index . 1 -}}
{{- if and $root.Values.ha $root.Values.ha.enabled -}}
podAntiAffinity:
  {{- if eq (default "soft" $root.Values.ha.podAntiAffinityMode) "hard" }}
  requiredDuringSchedulingIgnoredDuringExecution:
    - labelSelector:
        matchLabels:
          app.kubernetes.io/component: {{ $component }}
          app.kubernetes.io/instance: {{ $root.Release.Name }}
      topologyKey: {{ default "kubernetes.io/hostname" $root.Values.ha.topologyKey }}
  {{- else }}
  preferredDuringSchedulingIgnoredDuringExecution:
    - weight: 100
      podAffinityTerm:
        labelSelector:
          matchLabels:
            app.kubernetes.io/component: {{ $component }}
            app.kubernetes.io/instance: {{ $root.Release.Name }}
        topologyKey: {{ default "topology.kubernetes.io/zone" $root.Values.ha.topologyKey }}
    - weight: 50
      podAffinityTerm:
        labelSelector:
          matchLabels:
            app.kubernetes.io/component: {{ $component }}
            app.kubernetes.io/instance: {{ $root.Release.Name }}
        topologyKey: kubernetes.io/hostname
  {{- end }}
{{- end -}}
{{- end -}}

{{/*
Topology spread constraints block. Args: list of (component, root-context).
*/}}
{{- define "nms-custom.topologySpread" -}}
{{- $component := index . 0 -}}
{{- $root := index . 1 -}}
{{- if and $root.Values.ha $root.Values.ha.enabled $root.Values.ha.topologySpread $root.Values.ha.topologySpread.enabled -}}
topologySpreadConstraints:
  - maxSkew: {{ default 1 $root.Values.ha.topologySpread.maxSkew }}
    topologyKey: {{ default "topology.kubernetes.io/zone" $root.Values.ha.topologyKey }}
    whenUnsatisfiable: {{ default "ScheduleAnyway" $root.Values.ha.topologySpread.whenUnsatisfiable }}
    labelSelector:
      matchLabels:
        app.kubernetes.io/component: {{ $component }}
        app.kubernetes.io/instance: {{ $root.Release.Name }}
{{- end -}}
{{- end -}}

{{/*
API liveness/readiness probes. Args: root context only.
*/}}
{{- define "nms-custom.apiProbes" -}}
{{- $p := .Values.probes.api -}}
{{- if $p }}
livenessProbe:
  httpGet:
    path: {{ default "/healthz" $p.liveness.path }}
    port: 8000
    scheme: {{ if eq (default "true" .Values.config.httpsEnabled) "true" }}HTTPS{{ else }}HTTP{{ end }}
  initialDelaySeconds: {{ default 20 $p.liveness.initialDelaySeconds }}
  periodSeconds: {{ default 15 $p.liveness.periodSeconds }}
  timeoutSeconds: {{ default 3 $p.liveness.timeoutSeconds }}
  failureThreshold: {{ default 3 $p.liveness.failureThreshold }}
readinessProbe:
  httpGet:
    path: {{ default "/readyz" $p.readiness.path }}
    port: 8000
    scheme: {{ if eq (default "true" .Values.config.httpsEnabled) "true" }}HTTPS{{ else }}HTTP{{ end }}
  initialDelaySeconds: {{ default 10 $p.readiness.initialDelaySeconds }}
  periodSeconds: {{ default 10 $p.readiness.periodSeconds }}
  timeoutSeconds: {{ default 3 $p.readiness.timeoutSeconds }}
  failureThreshold: {{ default 3 $p.readiness.failureThreshold }}
{{- end -}}
{{- end -}}

{{/*
Frontend probes.
*/}}
{{- define "nms-custom.frontendProbes" -}}
{{- $p := .Values.probes.frontend -}}
{{- if $p }}
livenessProbe:
  httpGet: {path: {{ default "/" $p.liveness.path }}, port: 5173}
  initialDelaySeconds: {{ default 10 $p.liveness.initialDelaySeconds }}
  periodSeconds: {{ default 30 $p.liveness.periodSeconds }}
readinessProbe:
  httpGet: {path: {{ default "/" $p.readiness.path }}, port: 5173}
  initialDelaySeconds: {{ default 5 $p.readiness.initialDelaySeconds }}
  periodSeconds: {{ default 10 $p.readiness.periodSeconds }}
{{- end -}}
{{- end -}}
