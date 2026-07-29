import mathCatalogJson from "@/Knowledge/catalogs/math_textbook_chapters.json";
import provinceRoutesJson from "@/Knowledge/catalogs/province_exam_routes.json";
import textbookCatalogJson from "@/Knowledge/catalogs/textbook_catalog.json";
import taxonomyJson from "@/Knowledge/taxonomy/knowledge_taxonomy.json";
import type { SubjectKey } from "@/lib/types";

export const subjectLabels: Record<SubjectKey, string> = {
  chinese: "语文",
  mathematics: "数学",
  foreign_language: "英语",
  physics: "物理",
  chemistry: "化学",
  biology: "生物学",
  history: "历史",
  geography: "地理",
  ideology_politics: "思想政治",
  technology: "技术",
};

const subjectAliases: Record<string, SubjectKey> = {
  chinese: "chinese",
  mathematics: "mathematics",
  foreign_language: "foreign_language",
  english: "foreign_language",
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

export interface SubjectEdition {
  id: string;
  label: string;
  publisher: string;
  catalog_status: string;
  source_urls: string[];
  volumes: Array<{ id: string; label: string; chapters: ChapterOption[] }>;
}

interface TextbookSubject {
  subject: string;
  name: string;
  nature: string;
  publisher: string | null;
  edition: string | null;
  volumes: string[];
  candidate_editions?: string[];
}

export const provinceRoutes = provinceRoutesJson.provinces as ProvinceRoute[];
export const mathEditions = mathCatalogJson.editions as SubjectEdition[];

const textbookSubjects = textbookCatalogJson.subjects as TextbookSubject[];
const taxonomySubjects = taxonomyJson.subjects;
const compulsoryPlanningSubjects: SubjectKey[] = ["chinese", "mathematics", "foreign_language"];
const taxonomyKeys: Record<SubjectKey, string[]> = {
  chinese: ["chinese"],
  mathematics: ["mathematics"],
  foreign_language: ["english"],
  physics: ["physics"],
  chemistry: ["chemistry"],
  biology: ["biology"],
  history: ["history"],
  geography: ["geography"],
  ideology_politics: ["politics"],
  technology: ["information_technology", "general_technology"],
};
const textbookKeys: Record<SubjectKey, string[]> = { ...taxonomyKeys };
const editionIds: Record<string, string> = {
  "统编版": "unified",
  "人教版": "people_education",
  "外研版": "foreign_language_teaching",
  "译林版": "yilin",
  "北师大版": "beijing_normal",
  "苏教版": "jiangsu_education",
  "湘教版": "hunan_education",
  "鲁科版": "shandong_science",
  "粤教版": "guangdong_education",
  "教科版": "education_science",
  "沪科教版": "shanghai_science_education",
  "沪科版": "shanghai_science",
  "浙科版": "zhejiang_science",
  "中图版": "sinomaps",
  "鲁教版": "shandong_education",
};

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

export function planningSubjectKeys(selected: SubjectKey[]): SubjectKey[] {
  return [...compulsoryPlanningSubjects, ...selected];
}

export function defaultSubjects(route: ProvinceRoute): SubjectKey[] {
  if (route.exam_mode === "3+1+2") return ["physics", "chemistry", "biology"];
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
  if (targetGroup === "first") return [...selected.filter((item) => !first.has(item)), key];
  const secondSelected = selected.filter((item) => !first.has(item));
  const retainedSecond = secondSelected.length >= 2 ? secondSelected.slice(1) : secondSelected;
  return [...selected.filter((item) => first.has(item)), ...retainedSecond, key];
}

function textbookEntries(subject: SubjectKey): TextbookSubject[] {
  const keys = new Set(textbookKeys[subject]);
  return textbookSubjects.filter((item) => keys.has(item.subject));
}

export function subjectEditions(subject: SubjectKey): SubjectEdition[] {
  if (subject === "mathematics") return mathEditions;
  if (subject === "technology") {
    return [{
      id: "school_confirmed",
      label: "学校实际版本（待确认）",
      publisher: "须按浙江当地教学用书目录及学校版权页确认",
      catalog_status: "STANDARD_ONLY",
      source_urls: [],
      volumes: [],
    }];
  }
  const entries = textbookEntries(subject);
  const labels = entries.flatMap((entry) => (
    entry.candidate_editions?.length
      ? entry.candidate_editions
      : entry.edition ? [entry.edition] : []
  ));
  const uniqueLabels = [...new Set(labels)];
  return uniqueLabels.map((label, index) => ({
    id: editionIds[label] || `registered_${index + 1}`,
    label,
    publisher: entries.find((entry) => (
      entry.edition === label || entry.candidate_editions?.includes(label)
    ))?.publisher || "出版社须由学校版权页确认",
    catalog_status: "EDITION_REGISTERED",
    source_urls: [],
    volumes: [],
  }));
}

export function getSubjectEdition(subject: SubjectKey, id: string): SubjectEdition {
  const editions = subjectEditions(subject);
  return editions.find((item) => item.id === id) || editions[0];
}

export function progressGroups(subject: SubjectKey, editionId: string): ProgressGroup[] {
  const edition = getSubjectEdition(subject, editionId);
  if (subject === "mathematics" && edition.catalog_status === "VERIFIED_OFFICIAL") {
    return edition.volumes.map((volume) => ({
      id: volume.id,
      label: volume.label,
      options: volume.chapters,
    }));
  }
  return taxonomyKeys[subject].map((taxonomyKey) => {
    const taxonomy = taxonomySubjects.find((item) => item.subject === taxonomyKey);
    return {
      id: `curriculum_standard_${taxonomyKey}`,
      label: subject === "technology"
        ? `${taxonomy?.name || taxonomyKey}课程标准模块`
        : "课程标准模块（教材章序待学校确认）",
      options: (taxonomy?.modules || []).map((module) => ({ id: module.id, title: module.name })),
    };
  });
}

export function progressLabel(subject: SubjectKey, editionId: string, progressId: string): string {
  for (const group of progressGroups(subject, editionId)) {
    const found = group.options.find((item) => item.id === progressId);
    if (found) return `${group.label} · ${found.number ? `${found.number} ` : ""}${found.title}`;
  }
  return "未确认进度";
}

export function editionEvidenceLabel(subject: SubjectKey, editionId: string): string {
  const edition = getSubjectEdition(subject, editionId);
  if (subject === "mathematics" && edition.catalog_status === "VERIFIED_OFFICIAL") {
    const count = edition.volumes.reduce((sum, volume) => sum + volume.chapters.length, 0);
    return `${edition.publisher}官方目录已核验，共 ${edition.volumes.length} 册、${count} 章`;
  }
  if (subject === "technology") {
    return "技术包含信息技术与通用技术；当前使用两科教育部课程标准模块，实际教材须按浙江当地目录和学校版权页确认";
  }
  return `${subjectLabels[subject]}${edition.label}已登记，但完整章序待官方来源/学校版权页核验；当前仅使用教育部课程标准模块`;
}

export function subjectScoreMax(subject: SubjectKey): number {
  return compulsoryPlanningSubjects.includes(subject) ? 150 : 100;
}
