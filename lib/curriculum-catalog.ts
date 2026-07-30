import provinceRoutesJson from "@/Knowledge/catalogs/province_exam_routes.json";
import textbookPdfCatalogJson from "@/Knowledge/catalogs/textbook_pdf_catalog.json";
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
  evidence?: {
    source_pdf: string;
    pdf_page: number;
    extraction_method: string;
  };
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
  pdf_count?: number;
  chapter_count?: number;
  review_required_volume_count?: number;
  volumes: Array<{
    id: string;
    label: string;
    catalog_status?: string;
    source_pdf?: string;
    chapters: ChapterOption[];
  }>;
}

interface PdfSubjectCatalog {
  id: SubjectKey;
  label: string;
  editions: Array<Omit<SubjectEdition, "source_urls">>;
}

export const provinceRoutes = provinceRoutesJson.provinces as ProvinceRoute[];

const pdfSubjects = textbookPdfCatalogJson.subjects as PdfSubjectCatalog[];
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

export function subjectEditions(subject: SubjectKey): SubjectEdition[] {
  const catalog = pdfSubjects.find((item) => item.id === subject);
  return (catalog?.editions || []).map((edition) => ({ ...edition, source_urls: [] }));
}

export function getSubjectEdition(subject: SubjectKey, id: string): SubjectEdition {
  const editions = subjectEditions(subject);
  return editions.find((item) => item.id === id) || editions[0];
}

export function progressGroups(subject: SubjectKey, editionId: string): ProgressGroup[] {
  const edition = getSubjectEdition(subject, editionId);
  const textbookGroups = edition.volumes
    .filter((volume) => volume.chapters.length)
    .map((volume) => ({
      id: volume.id,
      label: `${volume.label}${
        volume.catalog_status === "VERIFIED_FROM_PDF_TOC" ? "" : " · 待复核"
      }`,
      options: volume.chapters,
    }));
  if (textbookGroups.length) return textbookGroups;
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

const knowledgeDimensionLabels: Record<string, string> = {
  foundation: "基础掌握",
  application: "综合应用",
};

export function knowledgeIdLabel(knowledgeId: string): string {
  const matched = knowledgeId.match(/^(.*)_(foundation|application)$/);
  const dimension = matched ? knowledgeDimensionLabels[matched[2]] : "";
  for (const subject of pdfSubjects) {
    for (const edition of subject.editions) {
      for (const volume of edition.volumes) {
        const chapter = volume.chapters.find((item) => (
          knowledgeId === item.id || knowledgeId.startsWith(`${item.id}_`)
        ));
        if (!chapter) continue;
        const chapterName = `${chapter.number ? `${chapter.number} ` : ""}${chapter.title}`;
        return [
          subject.label,
          edition.label,
          volume.label,
          chapterName,
          dimension,
        ].filter(Boolean).join(" · ");
      }
    }
  }
  return dimension ? `${matched?.[1]} · ${dimension}` : knowledgeId;
}

export function editionEvidenceLabel(subject: SubjectKey, editionId: string): string {
  const edition = getSubjectEdition(subject, editionId);
  const reviewCount = edition.review_required_volume_count || 0;
  const chapterCount = edition.chapter_count
    || edition.volumes.reduce((sum, volume) => sum + volume.chapters.length, 0);
  const evidence = `${edition.publisher}；本地教材 PDF 目录：${
    edition.pdf_count || edition.volumes.length
  } 册、${chapterCount} 个章节选项`;
  return reviewCount
    ? `${evidence}；其中 ${reviewCount} 册目录需人工复核，页面已明确标注`
    : `${evidence}，全部章名均可追溯到对应 PDF 目录页`;
}

export function subjectScoreMax(subject: SubjectKey): number {
  return compulsoryPlanningSubjects.includes(subject) ? 150 : 100;
}
