import { type GeneratedResource } from "../../api/resources";

export type StudioResourceFamily = {
  key: string;
  latest: GeneratedResource;
  versions: GeneratedResource[];
};

export function resourceFamilyKey(resource: GeneratedResource) {
  return resource.version_family_id || `legacy:${resource.id}`;
}

export function groupResourceVersions(resources: GeneratedResource[]): StudioResourceFamily[] {
  const grouped = new Map<string, GeneratedResource[]>();
  for (const resource of resources) {
    const key = resourceFamilyKey(resource);
    grouped.set(key, [...(grouped.get(key) ?? []), resource]);
  }
  return [...grouped.entries()]
    .map(([key, versions]) => {
      const ordered = [...versions].sort(compareResourceVersions);
      return { key, latest: ordered[0], versions: ordered };
    })
    .sort((left, right) => right.latest.created_at.localeCompare(left.latest.created_at));
}

export function compareResourceVersions(left: GeneratedResource, right: GeneratedResource) {
  const versionDelta = (right.version_number ?? 0) - (left.version_number ?? 0);
  return versionDelta || right.created_at.localeCompare(left.created_at) || Number(right.id) - Number(left.id);
}

export function versionLabel(resource: GeneratedResource) {
  return resource.version_number ? `v${resource.version_number}` : "历史版本";
}
