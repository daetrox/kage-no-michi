#include "game_lang.h"

#include "config.h"
#include "platform.h"

#include <cstdio>
#include <cstring>
#include <fstream>

namespace
{
constexpr const char* kSerial = "SLUS-00706";
constexpr uint32_t kOptionsByte = 0x10048; // bit 0x08: voces japonesas
constexpr size_t kBufferSize = 64;         // el búfer del subtítulo ocupa 0x40 bytes

// Cada ejecutable del juego se carga en 0x80011000; se reconocen por una instrucción del cargador
// de los CAD («addiu a1, a1, %lo("%sSTAGE%d%c.CAD")»).
struct Exe
{
  uint32_t check;      // dirección de esa instrucción
  uint16_t check_val;  // su mitad baja
  uint32_t path_addiu; // «addiu a2, a2, %lo("K:\WORK\CDIMAGE\ANIM\")»
  uint16_t path_lo;
  uint32_t free_str;   // cadena sin usar en la versión americana («…\start\Card_i.txt», 38 bytes)
  uint32_t subtitle;   // búfer con la frase que se está mostrando
  // Comando 8 de las escenas (copia la frase al búfer): «lui a0, %hi(búfer)» y «addiu a0, a0,
  // %lo(búfer)». En español se cambian para que copie a free_str (que el juego no dibuja) y el
  // launcher escribe la traducción en el búfer: así nunca se ve la frase inglesa. 0 = no se puede
  // (en MENU y ENDING el destino sólo se puede mover ±32 KB y no hay hueco libre a ese alcance).
  uint32_t copy_lui, copy_addiu;
};
const Exe kExes[] = {
  {0x80050144, 0x2E20, 0x80050150, 0x2E30, 0x80013270, 0x800C08A8, 0x8004FAB8, 0x8004FACC}, // MAIN.EXE (misiones)
  {0x80022744, 0x2078, 0x80022748, 0x2088, 0x80011B34, 0x800926F8, 0, 0},                   // MENU.EXE
  {0x800191F8, 0x18D4, 0x800191FC, 0x18E4, 0x8001197C, 0x80084B50, 0, 0},                   // ENDING.EXE
};

uint32_t Fnv1a(const std::string& s)
{
  uint32_t h = 0x811C9DC5u;
  for (unsigned char c : s)
    h = (h ^ c) * 0x01000193u;
  return h;
}

std::string Trim(const std::string& s)
{
  const size_t a = s.find_first_not_of(' ');
  if (a == std::string::npos)
    return "";
  return s.substr(a, s.find_last_not_of(' ') - a + 1);
}

// UTF-8 → Latin-1 (la codificación de la fuente del juego). ¿ y ¡ no existen en la fuente: se omiten.
std::string ToLatin1(const std::string& utf8)
{
  std::string out;
  for (size_t i = 0; i < utf8.size(); i++)
  {
    const unsigned char c = static_cast<unsigned char>(utf8[i]);
    uint32_t cp = c;
    if (c >= 0xC0 && c < 0xE0 && i + 1 < utf8.size())
      cp = ((c & 0x1F) << 6) | (static_cast<unsigned char>(utf8[++i]) & 0x3F);
    else if (c >= 0xE0 && i + 2 < utf8.size())
    {
      cp = ((c & 0x0F) << 12) | ((static_cast<unsigned char>(utf8[i + 1]) & 0x3F) << 6) |
           (static_cast<unsigned char>(utf8[i + 2]) & 0x3F);
      i += 2;
    }
    if (cp == 0xBF || cp == 0xA1)
      continue;
    if (cp == 0xAB || cp == 0xBB || cp == 0x201C || cp == 0x201D)
      cp = '"';
    else if (cp == 0x2018 || cp == 0x2019)
      cp = '\'';
    else if (cp > 0xFF || (cp >= 0x80 && cp < 0xC0))
      cp = '?';
    out += static_cast<char>(cp);
  }
  return out;
}
} // namespace

GameLanguage::Text GameLanguage::ParseText(const std::string& code)
{
  if (code == "es")
    return Text::Spanish;
  if (code == "fr")
    return Text::French;
  if (code == "it")
    return Text::Italian;
  return Text::English;
}

const char* GameLanguage::TextCode(Text t)
{
  switch (t)
  {
    case Text::Spanish: return "es";
    case Text::French: return "fr";
    case Text::Italian: return "it";
    default: return "en";
  }
}

bool GameLanguage::Supported(const std::string& serial)
{
  return serial == kSerial;
}

std::string GameLanguage::PathPatch(const std::string& serial, Text text)
{
  if (serial != kSerial || text == Text::English)
    return "";
  std::string code;
  char line[48];
  auto add = [&](const Exe& e, uint32_t addr, uint16_t value) {
    // Sólo si está cargado ese ejecutable (los tres comparten las mismas direcciones).
    std::snprintf(line, sizeof(line), "%sD0%06X %04X+80%06X %04X", code.empty() ? "" : "+", e.check & 0xFFFFFF,
                  e.check_val, addr & 0xFFFFFF, value);
    code += line;
  };
  if (text == Text::Spanish)
  {
    for (const Exe& e : kExes)
      if (e.copy_lui)
      {
        add(e, e.copy_lui, static_cast<uint16_t>((e.free_str + 0x8000) >> 16));
        add(e, e.copy_addiu, static_cast<uint16_t>(e.free_str & 0xFFFF));
      }
    return code;
  }
  std::string path = text == Text::French ? "K:\\WORK\\CDIMAGE\\ANIM\\FRENCH\\" : "K:\\WORK\\CDIMAGE\\ANIM\\ITALIAN\\";
  path.append(2 - path.size() % 2, '\0'); // terminada en cero y de longitud par
  for (const Exe& e : kExes)
  {
    for (size_t i = 0; i < path.size(); i += 2)
      add(e, e.free_str + static_cast<uint32_t>(i),
          static_cast<uint16_t>(static_cast<unsigned char>(path[i]) | (static_cast<unsigned char>(path[i + 1]) << 8)));
    add(e, e.path_addiu, static_cast<uint16_t>(e.free_str & 0xFFFF));
  }
  return code;
}

void GameLanguage::SetGame(const std::string& serial, Text text, bool japanese_voices, const std::string& assets_dir)
{
  m_active = serial == kSerial;
  m_japanese = japanese_voices;
  m_text = text;
  m_last.clear();
  m_table.clear();
  if (!m_active || text != Text::Spanish)
    return;
  std::ifstream f(Platform::Path(assets_dir + "/lang/" + TextCode(text) + ".txt"));
  std::string line;
  while (std::getline(f, line))
  {
    if (line.empty() || line[0] == '#')
      continue;
    const size_t tab = line.find('\t');
    if (tab == std::string::npos)
      continue;
    const uint32_t h = static_cast<uint32_t>(std::strtoul(line.substr(0, tab).c_str(), nullptr, 16));
    std::string tr = ToLatin1(line.substr(tab + 1));
    if (tr.size() >= kBufferSize)
      tr.resize(kBufferSize - 1);
    m_table[h] = tr;
  }
}

void GameLanguage::OnFrame(uint8_t* ram, size_t size)
{
  if (!m_active || !ram || size < 0x200000)
    return;
  if (m_japanese)
    ram[kOptionsByte] |= 0x08;
  if (m_table.empty())
    return;
  auto half = [&](uint32_t a) { return static_cast<uint16_t>(ram[a & 0x1FFFFF] | (ram[(a + 1) & 0x1FFFFF] << 8)); };
  for (const Exe& e : kExes)
  {
    if (half(e.check) != e.check_val)
      continue;
    char* buf = reinterpret_cast<char*>(ram + (e.subtitle & 0x1FFFFF));
    // Frase nueva copiada al búfer intermedio (comando 8 redirigido): se traduce al búfer real.
    if (e.copy_lui)
    {
      char* stage = reinterpret_cast<char*>(ram + (e.free_str & 0x1FFFFF));
      if (stage[0] == 'K' && stage[1] == ':')
        stage[0] = 0; // aún la cadena original del juego (sin usar)
      if (stage[0])
      {
        const std::string en(stage, strnlen(stage, kBufferSize - 1));
        const auto it = m_table.find(Fnv1a(Trim(en)));
        const std::string& out = it != m_table.end() ? it->second : en;
        std::memcpy(buf, out.c_str(), out.size() + 1);
        m_last = out;
        stage[0] = 0;
        return;
      }
    }
    // Si el juego la copió directamente al búfer (antes de aplicarse el parche, o en MENU/ENDING),
    // se sustituye allí; el juego llega a dibujar la inglesa durante un frame.
    const std::string cur(buf, strnlen(buf, kBufferSize));
    if (cur.empty() || cur == m_last)
      return;
    const auto it = m_table.find(Fnv1a(Trim(cur)));
    if (it == m_table.end())
      return;
    std::memcpy(buf, it->second.c_str(), it->second.size() + 1);
    m_last = it->second;
    return;
  }
}
