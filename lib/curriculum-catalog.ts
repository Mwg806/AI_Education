import mathCatalogJson from "@/Knowledge/catalogs/math_textbook_chapters.json";
import provinceRoutesJson from "@/Knowledge/catalogs/province_exam_routes.json";
import taxonomyJson from "@/Knowledge/taxonomy/knowledge_taxonomy.json";
import type { SubjectKey } from "@/lib/types";

export const subjectLabels: Record<SubjectKey, string> = {
  physics: "物理",
  chemistry: "化学",
  biology: "生物",
  history: "历史",
  geography: "地理",
  ideology_politics: "思想政治",
  technology: "技术",
};

const subjectAliases: Record<string, SubjectKey> = {
  physics: "physics",
  chemistry: "chemistry",
  biology: "biology",
  history: "history",
  geography: "geography",
  politics: "ideology_politics",
  technology: "technology",
};

export interface ProvinceRoute {
  code: string;
  slug: string;
  name: string;
  exam_mode: "3+3" | "3+1+2";
  official_authority: string;
  official_url: string;
  elective_subjects?: string[];
  first_choice_subjects?: string[];
  second_choice_subjects?: string[];
  selection_rule: string;
}

export interface ChapterOption {
  id: string;
  number?: string;
  title: string;
}

export interface ProgressGroup {
  id: string;
  label: string;
  options: ChapterOption[];
}

export interface MathEdition {
  id: string;
  label: string;
  publisher: string;
  catalog_status: string;
  source_urls: string[];
  volumes: Array<{ id: string; label: string; chapters: ChapterOption[] }>;
}

export const provinceRoutes = provinceRoutesJson.provinces as ProvinceRoute[];
export const mathEditions = mathCatalogJson.editions as MathEdition[];

const mathematicsTaxonomy = taxonomyJson.subjects.find(
  (subject) => subject.subject === "mathematics",
);

export function getProvinceRoute(code: string): ProvinceRoute {
  return provinceRoutes.find((item) => item.code === code) || provinceRoutes[0];
}

export function provinceSubjectKeys(route: ProvinceRoute): SubjectKey[] {
  const raw = route.elective_subjects || [
    ...(route.first_choice_subjects || []),
    ...(route.second_choice_subjects || []),
  ];
  return raw.map((item) => subjectAliases[item]).filter(Boolean);
}

export function defaultSubjects(route: ProvinceRoute): SubjectKey[] {
  if (route.exam_mode === "3+1+2") {
    return ["physics", "chemistry", "biology"];
  }
  return provinceSubjectKeys(route).slice(0, 3);
}

export function isSubjectSelectionValid(route: ProvinceRoute, selected: SubjectKey[]): boolean {
  if (selected.length !== 3) return false;
  const allowed = new Set(provinceSubjectKeys(route));
  if (!selected.every((item) => allowed.has(item))) return false;
  if (route.exam_mode === "3+3") return true;
  const first = new Set((route.first_choice_subjects || []).map((item) => subjectAliases[item]));
  const second = new Set((route.second_choice_subjects || []).map((item) => subjectAliases[item]));
  return selected.filter((item) => first.has(item)).length === 1
    && selected.filter((item) => second.has(item)).length === 2;
}

export function selectProvinceSubject(
  route: ProvinceRoute,
  selected: SubjectKey[],
  key: SubjectKey,
): SubjectKey[] {
  if (route.exam_mode === "3+3") {
    if (selected.includes(key)) return selected.filter((item) => item !== key);
    return [...selected, key].slice(-3);
  }
  const first = new Set((route.first_choice_subjects || []).map((item) => subjectAliases[item]));
  const targetGroup = first.has(key) ? "first" : "second";
  if (selected.includes(key)) return selected.filter((item) => item !== key);
  if (targetGroup === "first") {
    return [...selected.filter((item) => !first.has(item)), key];
  }
  const secondSelected = selected.filter((item) => !first.has(item));
  const retainedSecond = secondSelected.length >= 2 ? secondSelected.slice(1) : secondSelected;
  return [...selected.filter((item) => first.has(item)), ...retainedSecond, key];
}

export function getMathEdition(id: string): MathEdition {
  return mathEditions.find((item) => item.id === id) || mathEditions[0];
}

export function progressGroups(editionId: string): ProgressGroup[] {
  const edition = getMathEdition(editionId);
  if (edition.catalog_status === "VERIFIED_OFFICIAL") {
    return edition.volumes.map((volume) => ({
      id: volume.id,
      label: volume.label,
      options: volume.chapters,
    }));
  }
  return [{
    id: "curriculum_standard",
    label: "课程标准主题（教材章序待学校确认）",
    options: (mathematicsTaxonomy?.modules || []).map((module) => ({
      id: module.id,
      title: module.name,
    })),
  }];
}

export function progressLabel(editionId: string, progressId: string): string {
  for (const group of progressGroups(editionId)) {
    const found = group.options.find((item) => item.id === progressId);
    if (found) return `${group.label} · ${found.number ? `${found.number} ` : ""}${found.title}`;
  }
  return "未确认进度";
}

export function editionEvidenceLabel(editionId: string): string {
  const edition = getMathEdition(editionId);
  if (edition.catalog_status === "VERIFIED_OFFICIAL") {
    const count = edition.volumes.reduce((sum, volume) => sum + volume.chapters.length, 0);
    return `${edition.publisher}官方目录已核验，共 ${edition.volumes.length} 册、${count} 章`;
  }
  return `${edition.label}册次已登记，但完整章序待官方来源/学校版权页核验；当前仅使用国家课程标准主题`;
}
