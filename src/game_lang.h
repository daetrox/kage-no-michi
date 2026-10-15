// Idioma de Tenchu: Stealth Assassins (EE. UU., SLUS-00706) dentro del juego.
//
// Voces: el disco trae las voces japonesas de las escenas (XA\EVENTJ.XA). El juego las usa si el
//   bit 0x08 de 0x80010048 está activo (en el original, con un truco secreto del menú); las escenas
//   que no tienen versión japonesa siguen en inglés.
// Subtítulos de las escenas (ANIM\STAGE<n><R|A>.CAD):
//   - francés e italiano: el disco americano conserva los CAD europeos en ANIM\FRENCH\ y
//     ANIM\ITALIAN\. Se cambia la carpeta de la que se cargan (códigos GameShark condicionales).
//   - español: el juego copia cada frase a un búfer fijo antes de dibujarla; el launcher la
//     sustituye por su traducción (assets/lang/es.txt, indexada por un hash de la frase inglesa).
//   La fuente del juego tiene las letras latinas con tilde y la ñ (no ¿ ni ¡).
#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <unordered_map>

class GameLanguage
{
public:
  enum class Text
  {
    English,
    Spanish,
    French,
    Italian,
  };

  static Text ParseText(const std::string& code); // "en", "es", "fr", "it"
  static const char* TextCode(Text t);
  static bool Supported(const std::string& serial);

  // Códigos GameShark que cambian la carpeta de los subtítulos (vacío si no hace falta).
  static std::string PathPatch(const std::string& serial, Text text);

  // Prepara la sesión de juego; carga la traducción si hace falta.
  void SetGame(const std::string& serial, Text text, bool japanese_voices, const std::string& assets_dir);
  // Tras cada frame: aplica las voces y sustituye el subtítulo en curso.
  void OnFrame(uint8_t* ram, size_t size);

private:
  bool m_active = false;
  bool m_japanese = false;
  Text m_text = Text::English;
  std::unordered_map<uint32_t, std::string> m_table; // hash de la frase inglesa → Latin-1
  std::string m_last;                                 // última frase escrita por el launcher
};
