import { parse } from "@babel/parser";
import fs from "node:fs";

const code = fs.readFileSync(0, "utf8");
const ast = parse(code, {
  sourceType: "unambiguous",
  plugins: ["jsx", "typescript"],
  errorRecovery: true,
});

function infer(node) {
  if (!node) return ["unknown", null];
  if (node.type === "StringLiteral") return ["string", node.value];
  if (node.type === "NumericLiteral") return ["number", node.value];
  if (node.type === "BooleanLiteral") return ["boolean", node.value];
  if (node.type === "NullLiteral") return ["null", null];
  if (node.type === "TemplateLiteral" && node.expressions.length === 0) {
    return ["string", node.quasis[0].value.cooked];
  }
  return ["unknown", null];
}

function calleeName(callee) {
  if (!callee) return null;
  if (callee.type === "Identifier") return callee.name;
  if (callee.type === "MemberExpression" && !callee.computed && callee.property.type === "Identifier") {
    return callee.property.name;
  }
  return null;
}

const trackingFunctions = new Set(
  (process.env.TRACKING_FUNCTIONS || "trackEvent")
    .split(",")
    .map((name) => name.trim().split(".").pop())
    .filter(Boolean),
);

const events = [];

function walk(node) {
  if (!node || typeof node !== "object") return;
  if (node.type === "CallExpression" && trackingFunctions.has(calleeName(node.callee))) {
    const [nameArg, propsArg] = node.arguments;
    const parameters = {};
    const paramTypes = {};
    let dynamic = false;
    if (propsArg?.type === "ObjectExpression") {
      for (const property of propsArg.properties) {
        if (property.type !== "ObjectProperty" || property.computed) {
          dynamic = true;
          continue;
        }
        const key =
          property.key.type === "Identifier"
            ? property.key.name
            : property.key.type === "StringLiteral"
              ? property.key.value
              : null;
        if (!key) {
          dynamic = true;
          continue;
        }
        const [type, value] = infer(property.value);
        parameters[key] = value;
        paramTypes[key] = type;
        if (type === "unknown") dynamic = true;
      }
    } else if (propsArg) {
      dynamic = true;
    }
    events.push({
      event_name: nameArg?.type === "StringLiteral" ? nameArg.value : null,
      parameters,
      param_types: paramTypes,
      line: node.loc?.start?.line ?? null,
      dynamic,
    });
  }
  for (const value of Object.values(node)) {
    if (Array.isArray(value)) value.forEach(walk);
    else if (value && typeof value === "object" && value.type) walk(value);
  }
}

walk(ast);
process.stdout.write(JSON.stringify(events));
