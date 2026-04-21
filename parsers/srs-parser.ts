import fs from "fs";
import type {
  SRSDocument,
  Requirement,
  Module,
  DataEntity,
  APIContract,
} from "@/types";

export class SRSParser {
  parse(filePath: string): SRSDocument {
    if (!fs.existsSync(filePath)) {
      throw new Error(`SRS file not found: ${filePath}`);
    }

    const raw = JSON.parse(fs.readFileSync(filePath, "utf-8")) as Record<string, unknown>;
    return this.normalize(raw);
  }

  private normalize(raw: Record<string, unknown>): SRSDocument {
    const doc: SRSDocument = {
      projectName: this.extractString(raw, ["projectName", "project_name", "name", "title"]) || "Unknown Project",
      version: this.extractString(raw, ["version", "srsVersion"]),
      actors: this.extractStringArray(raw, ["actors", "users", "stakeholders"]),
      functionalRequirements: this.extractRequirements(raw, [
        "functionalRequirements",
        "functional_requirements",
        "fr",
        "requirements",
      ]),
      nonFunctionalRequirements: this.extractRequirements(raw, [
        "nonFunctionalRequirements",
        "non_functional_requirements",
        "nfr",
        "nonFunctional",
      ]),
      modules: this.extractModules(raw),
      dataEntities: this.extractDataEntities(raw),
      apiContracts: this.extractAPIContracts(raw),
      constraints: this.extractStringArray(raw, ["constraints", "limitations"]),
      raw,
    };

    if (doc.functionalRequirements.length === 0) {
      doc.functionalRequirements = this.deepExtractRequirements(raw);
    }

    return doc;
  }

  private extractString(obj: Record<string, unknown>, keys: string[]): string | undefined {
    for (const key of keys) {
      if (typeof obj[key] === "string" && obj[key]) return obj[key] as string;
    }
    return undefined;
  }

  private extractStringArray(obj: Record<string, unknown>, keys: string[]): string[] {
    for (const key of keys) {
      const val = obj[key];
      if (Array.isArray(val)) {
        return val.filter((v) => typeof v === "string") as string[];
      }
    }
    return [];
  }

  private extractRequirements(obj: Record<string, unknown>, keys: string[]): Requirement[] {
    for (const key of keys) {
      const val = obj[key];
      if (Array.isArray(val) && val.length > 0) {
        return val.map((item, i) => this.normalizeRequirement(item, i, key));
      }
    }
    return [];
  }

  private normalizeRequirement(
    item: unknown,
    index: number,
    prefix: string
  ): Requirement {
    if (typeof item === "string") {
      return {
        id: `${prefix.toUpperCase().substring(0, 2)}-${index + 1}`,
        title: item.substring(0, 80),
        description: item,
        priority: "must",
      };
    }

    const obj = item as Record<string, unknown>;
    return {
      id:
        (this.extractString(obj, ["id", "req_id", "requirementId"]) ||
          `REQ-${index + 1}`),
      title:
        this.extractString(obj, ["title", "name", "summary"]) ||
        `Requirement ${index + 1}`,
      description:
        this.extractString(obj, ["description", "detail", "text", "content"]) ||
        JSON.stringify(obj),
      priority: this.normalizePriority(
        this.extractString(obj, ["priority", "importance", "level"])
      ),
      module: this.extractString(obj, ["module", "area", "category"]),
      category: this.extractString(obj, ["type", "category"]),
    };
  }

  private normalizePriority(p?: string): Requirement["priority"] {
    if (!p) return "must";
    const lower = p.toLowerCase();
    if (lower.includes("must") || lower.includes("high") || lower.includes("critical")) return "must";
    if (lower.includes("should") || lower.includes("medium")) return "should";
    if (lower.includes("could") || lower.includes("low")) return "could";
    if (lower.includes("wont") || lower.includes("optional")) return "wont";
    return "must";
  }

  private extractModules(obj: Record<string, unknown>): Module[] {
    const keys = ["modules", "features", "components", "sections"];
    for (const key of keys) {
      const val = obj[key];
      if (Array.isArray(val) && val.length > 0) {
        return val.map((item, i) => {
          const o = item as Record<string, unknown>;
          return {
            id: (this.extractString(o, ["id", "moduleId"]) || `M-${i + 1}`),
            name: this.extractString(o, ["name", "title"]) || `Module ${i + 1}`,
            description: this.extractString(o, ["description"]) || "",
            requirements: this.extractStringArray(o, ["requirements", "req_ids"]),
          };
        });
      }
    }
    return [];
  }

  private extractDataEntities(obj: Record<string, unknown>): DataEntity[] {
    const keys = ["dataEntities", "entities", "models", "schemas", "data_models"];
    for (const key of keys) {
      const val = obj[key];
      if (Array.isArray(val) && val.length > 0) {
        return val.map((item) => {
          const o = item as Record<string, unknown>;
          return {
            name: this.extractString(o, ["name", "entity", "model"]) || "Unknown",
            fields: Array.isArray(o.fields)
              ? (o.fields as Array<Record<string, unknown>>).map((f) => ({
                  name: this.extractString(f, ["name"]) || "field",
                  type: this.extractString(f, ["type"]) || "string",
                  required: Boolean(f.required),
                }))
              : undefined,
          };
        });
      }
    }
    return [];
  }

  private extractAPIContracts(obj: Record<string, unknown>): APIContract[] {
    const keys = ["apiContracts", "api_contracts", "endpoints", "apis", "routes"];
    for (const key of keys) {
      const val = obj[key];
      if (Array.isArray(val) && val.length > 0) {
        return val.map((item) => {
          const o = item as Record<string, unknown>;
          return {
            path: this.extractString(o, ["path", "endpoint", "url"]) || "/",
            method: (this.extractString(o, ["method", "verb"]) || "GET").toUpperCase(),
            description: this.extractString(o, ["description", "summary"]),
          };
        });
      }
    }
    return [];
  }

  private deepExtractRequirements(obj: Record<string, unknown>): Requirement[] {
    const results: Requirement[] = [];
    let counter = 0;
    const walk = (node: unknown, depth = 0): void => {
      if (depth > 5 || results.length > 100) return;
      if (!node || typeof node !== "object") return;
      if (Array.isArray(node)) {
        node.forEach((item) => walk(item, depth + 1));
        return;
      }
      const o = node as Record<string, unknown>;
      const text = this.extractString(o, ["requirement", "description", "text", "content", "detail"]);
      if (text && text.length > 10) {
        counter++;
        results.push({
          id: `REQ-${counter}`,
          title: text.substring(0, 80),
          description: text,
        });
      } else {
        Object.values(o).forEach((v) => walk(v, depth + 1));
      }
    };
    walk(obj);
    return results;
  }
}
