#!/usr/bin/env bash
# Install the standalone CLI, never create or modify a website.
set -euo pipefail
repo="techreloaded-ar/websmith-cli"
version="${WEBSMITH_VERSION:-latest}"
install_dir="${WEBSMITH_INSTALL_DIR:-$HOME/.local/bin}"
case "$(uname -s)" in
  Darwin) os=darwin ;;
  Linux) os=linux ;;
  *) echo 'Sistema non supportato da setup.sh. Su Windows scarica la versione ZIP dalla release GitHub.' >&2; exit 1 ;;
esac
case "$(uname -m)" in
  arm64|aarch64) cpu=arm64 ;;
  x86_64|amd64) cpu=x64 ;;
  *) echo 'Architettura non supportata.' >&2; exit 1 ;;
esac
case "$os-$cpu" in darwin-arm64|darwin-x64|linux-x64) ;; *) echo "Versione non disponibile: $os-$cpu" >&2; exit 1 ;; esac
for tool in unzip awk mktemp; do
  command -v "$tool" >/dev/null || { echo "Comando richiesto: $tool" >&2; exit 1; }
done
if command -v sha256sum >/dev/null; then hash_tool=sha256sum
elif command -v shasum >/dev/null; then hash_tool=shasum
else echo 'Serve sha256sum oppure shasum.' >&2; exit 1; fi
asset="websmith-$os-$cpu.zip"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
# gh handles private repository authentication; curl is sufficient for public releases.
if command -v gh >/dev/null && gh auth status >/dev/null 2>&1; then
  args=(release download --repo "$repo" --dir "$tmp" --pattern "$asset" --pattern SHA256SUMS)
  if [ "$version" != latest ]; then args+=("$version"); fi
  gh "${args[@]}"
else
  command -v curl >/dev/null || { echo 'Serve curl oppure GitHub CLI (gh).' >&2; exit 1; }
  if [ "$version" = latest ]; then base="https://github.com/$repo/releases/latest/download"
  else base="https://github.com/$repo/releases/download/$version"; fi
  for file in "$asset" SHA256SUMS; do
    curl -fsSL --retry 3 "$base/$file" -o "$tmp/$file" || {
      echo 'Download non riuscito. Se il repository è privato, installa gh ed esegui gh auth login.' >&2
      exit 1
    }
  done
fi
expected=$(awk -v name="$asset" '$2 == name {print $1}' "$tmp/SHA256SUMS")
if [ "$hash_tool" = shasum ]; then actual=$(shasum -a 256 "$tmp/$asset" | awk '{print $1}')
else actual=$(sha256sum "$tmp/$asset" | awk '{print $1}'); fi
[ -n "$expected" ] && [ "$expected" = "$actual" ] || { echo 'Checksum non valido: installazione annullata.' >&2; exit 1; }
# Extract only the expected executable, never archive-supplied directories.
unzip -p "$tmp/$asset" websmith > "$tmp/websmith"
chmod 755 "$tmp/websmith"
"$tmp/websmith" --version
mkdir -p "$install_dir"
# Stage on the destination filesystem and replace only after successful verification.
staged=$(mktemp "$install_dir/.websmith.XXXXXX")
trap 'rm -rf "$tmp"; if [ -n "${staged:-}" ]; then rm -f "$staged"; fi' EXIT
cp "$tmp/websmith" "$staged"
chmod 755 "$staged"
mv -f "$staged" "$install_dir/websmith"
echo "Websmith installato in $install_dir/websmith"
case ":$PATH:" in *":$install_dir:"*) ;; *)
  echo "Aggiungi al PATH la cartella $install_dir per eseguire websmith da ogni cartella." ;;
esac
