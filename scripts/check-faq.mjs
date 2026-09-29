import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const faqPath = path.join(root, "mobile", "faq.html");
const homePath = path.join(root, "mobile", "landing.html");
const sitemapPath = path.join(root, "mobile", "sitemap.xml");
const llmsPath = path.join(root, "mobile", "llms.txt");
const faqUrl = "https://jarvis.agenthaus.io/faq";
const failures = [];

function fail(message) {
  failures.push(message);
}

function read(file) {
  return fs.readFileSync(file, "utf8");
}

function decode(value) {
  return value
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#x27;|&#39;|&apos;/g, "'")
    .replace(/&#(\d+);/g, (_, code) => String.fromCharCode(Number(code)))
    .replace(/&#x([0-9a-f]+);/gi, (_, code) => String.fromCharCode(parseInt(code, 16)));
}

function shown(html) {
  return decode(html.replace(/<[^>]+>/g, "")).replace(/\s+/g, " ").trim();
}

function jsonLdBlocks(html) {
  const blocks = [];
  const pattern = /<script\s+type="application\/ld\+json">([\s\S]*?)<\/script>/gi;
  for (const match of html.matchAll(pattern)) {
    blocks.push(JSON.parse(match[1]));
  }
  return blocks;
}

function faqPages(html) {
  const found = [];
  for (const block of jsonLdBlocks(html)) {
    const nodes = block["@graph"] || [block];
    for (const node of nodes) {
      const types = [].concat(node["@type"] || []);
      if (types.includes("FAQPage")) found.push(node);
    }
  }
  return found;
}

const faqHtml = read(faqPath);
const homeHtml = read(homePath);

if (faqPages(homeHtml).length) {
  fail("homepage still has an FAQPage schema after the questions moved to /faq");
}

if (/What is an AI sommelier for hotels, resorts, and cruise lines\?/.test(homeHtml)) {
  fail("homepage still contains an FAQ question");
}

const homeLink = [...homeHtml.matchAll(/<a\b[^>]*href="([^"]+)"[^>]*>([\s\S]*?)<\/a>/gi)]
  .find((match) => match[1] === "/faq" && shown(match[2]) === "Questions? See our FAQ");
if (!homeLink) {
  fail('homepage is missing a link to /faq with the text "Questions? See our FAQ"');
}

if (/class="faq"[^>]*\shidden\b/.test(faqHtml) || /<body[^>]*\shidden\b/.test(faqHtml)) {
  fail("FAQ page hides the questions");
}
if (/\.faq(?:-item)?\s*\{[^}]*display\s*:\s*none/.test(faqHtml)) {
  fail("FAQ page CSS hides the questions");
}

const pages = faqPages(faqHtml);
if (pages.length !== 1) {
  fail(`FAQ page should have one FAQPage schema, found ${pages.length}`);
}

const schema = pages[0] ? pages[0].mainEntity || [] : [];
const visible = [...faqHtml.matchAll(/<div class="faq-item">\s*<h2>([\s\S]*?)<\/h2>\s*<p>([\s\S]*?)<\/p>\s*<\/div>/gi)]
  .map((match) => ({ question: shown(match[1]), answer: shown(match[2]) }));

if (schema.length !== visible.length) {
  fail(`schema has ${schema.length} questions and the page shows ${visible.length}`);
}

const count = Math.max(schema.length, visible.length);
for (let i = 0; i < count; i += 1) {
  const fromSchema = schema[i];
  const fromPage = visible[i];
  const schemaQuestion = fromSchema ? shown(String(fromSchema.name || "")) : "";
  const schemaAnswer = fromSchema ? shown(String(fromSchema.acceptedAnswer?.text || "")) : "";
  const pageQuestion = fromPage ? fromPage.question : "";
  const pageAnswer = fromPage ? fromPage.answer : "";
  if (schemaQuestion !== pageQuestion) {
    fail(`question ${i + 1} does not match\n  schema: ${schemaQuestion}\n  page:   ${pageQuestion}`);
  }
  if (schemaAnswer !== pageAnswer) {
    fail(`answer ${i + 1} does not match\n  schema: ${schemaAnswer}\n  page:   ${pageAnswer}`);
  }
}

if (!read(sitemapPath).includes(faqUrl)) {
  fail(`sitemap.xml is missing ${faqUrl}`);
}
if (!read(llmsPath).includes(faqUrl)) {
  fail(`llms.txt is missing ${faqUrl}`);
}

if (failures.length) {
  console.error(failures.join("\n\n"));
  process.exit(1);
}

console.log(`FAQ schema matches ${visible.length} visible questions, and ${faqUrl} is linked from the homepage, sitemap.xml, and llms.txt.`);
