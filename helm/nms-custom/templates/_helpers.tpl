{{- define "nms-custom.name" -}}nms-custom{{- end -}}
{{- define "nms-custom.labels" -}}
app.kubernetes.io/name: {{ include "nms-custom.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}
