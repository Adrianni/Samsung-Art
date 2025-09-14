<h1>Frame Art Uploader 🖼️📺</h1>
<p>Last opp kunst/bilder til <strong>Samsung The Frame</strong> via kommandolinjen. Støtter enten en lokal bildefil, et tilfeldig <em>Bing Wallpaper</em>, eller et landskapsbilde fra <em>Unsplash</em> (tilfeldig eller spesifikt). Skriptet beskjærer/tilpasser automatisk til 3840×2160 (4K) før opplasting, og husker tidligere opplastede bilder i <code>uploaded_files.json</code>.</p>

<hr>

<h2>🔧 Forutsetninger</h2>
<ul>
  <li>Python 3.9+</li>
  <li>TV og maskin på samme nettverk</li>
  <li>TV-en må støtte og (helst) være i <em>Art Mode</em></li>
  <li>Unsplash API access key (kun hvis du bruker <code>--unsplash [IMAGE_ID]</code>)</li>
</ul>

<h2>📦 Installering</h2>
<pre><code># (valgfritt, anbefalt) virtuelt miljø
python3 -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate

# Installer avhengigheter
pip install -r requirements.txt
</code></pre>

<hr>

<h2>▶️ Bruk</h2>
<p>Kjør skriptet med <code>--tvip</code> og <em>én</em> av kildene <code>--bingwallpaper</code>, <code>--unsplash [IMAGE_ID]</code> eller <code>--image &lt;sti&gt;</code>.</p>

<p>For <code>--unsplash [IMAGE_ID]</code> trenger du en <em>Unsplash API access key</em>. Sett den i miljøvariabelen <code>UNSPLASH_ACCESS_KEY</code> eller direkte i <code>frame_art_uploader.py</code>.</p>

<h3>Eksempler</h3>
<pre><code><h3>1) Bruk et tilfeldig Bing-bakgrunnsbilde på én TV</h3>
python3 frame_art_uploader.py --tvip 192.168.1.20 --bingwallpaper

<h3>2) Last opp en lokal bildefil</h3>
python3 frame_art_uploader.py --tvip 192.168.1.20 --image /path/til/bilde.jpg

<h3>3) Bruk et tilfeldig Unsplash-landsbilde</h3>
# forutsetter at UNSPLASH_ACCESS_KEY er satt
export UNSPLASH_ACCESS_KEY=din_nokkel
python3 frame_art_uploader.py --tvip 192.168.1.20 --unsplash

<h3>4) Bruk et spesifikt Unsplash-bilde via ID</h3>
python3 frame_art_uploader.py --tvip 192.168.1.20 --unsplash a-body-of-water-surrounded-by-trees-on-a-sunny-day-Pyk2RVJ5fVY

<h3>5) Flere TV-er (kommaseparert liste)</h3>
python3 frame_art_uploader.py --tvip 192.168.1.20,192.168.1.21 --bingwallpaper

<h3>6) Debug (mer logging)</h3>
python3 frame_art_uploader.py --tvip 192.168.1.20 --bingwallpaper --debug
</code></pre>

<hr>

<h2>⚙️ Argumenter</h2>
<table>
  <thead>
    <tr>
      <th>Flagg</th>
      <th>Påkrevd</th>
      <th>Beskrivelse</th>
      <th>Eksempel</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><code>--tvip</code></td>
      <td>Ja</td>
      <td>IP til én eller flere TV-er (kommaseparert)</td>
      <td><code>--tvip 192.168.1.20,192.168.1.21</code></td>
    </tr>
    <tr>
      <td><code>--bingwallpaper</code></td>
      <td>Ja* (enten/eller)</td>
      <td>Bruk et tilfeldig Bing Wallpaper (hentes via HTTP)</td>
      <td><code>--bingwallpaper</code></td>
    </tr>
    <tr>
      <td><code>--unsplash [IMAGE_ID]</code></td>
      <td>Ja* (enten/eller)</td>
      <td>Bruk et Unsplash-bilde. Oppgi IMAGE_ID for et spesifikt bilde eller utelat for et tilfeldig landskap (krever UNSPLASH_ACCESS_KEY)</td>
      <td><code>--unsplash</code> eller <code>--unsplash a-body-of-water-surrounded-by-trees-on-a-sunny-day-Pyk2RVJ5fVY</code></td>
    </tr>
    <tr>
      <td><code>--image &lt;sti&gt;</code></td>
      <td>Ja* (enten/eller)</td>
      <td>Bruk en lokal bildefil</td>
      <td><code>--image /path/til/bilde.jpg</code></td>
    </tr>
    <tr>
      <td><code>--debug</code></td>
      <td>Nei</td>
      <td>Aktiver mer detaljert logging (nyttig for feilsøk)</td>
      <td><code>--debug</code></td>
    </tr>
  </tbody>
</table>

<hr>

<h2>🖼️ Bildetilpasning</h2>
<ul>
  <li>Bilder skaleres og midt-beskjæres automatisk til <strong>3840×2160</strong> (JPEG, kvalitet 90).</li>
  <li>Loddrett/kvadratisk motiv beskjæres i kantene for å passe 16:9 (The Frame).</li>
</ul>

<hr>

<h2>🧠 Gjenbruk av opplasting</h2>
<p>Skriptet lagrer metadata i <code>uploaded_files.json</code> for å kunne gjenbruke tidligere opplastede bilder (per kilde, og per TV ved flere TV-er).</p>

<hr>

<h2>🧯 Feilsøking</h2>
<ul>
  <li><strong>Får ikke kontakt:</strong> Verifiser IP (<code>ping</code>), at TV og maskin er på samme VLAN/subnett, og prøv <code>--debug</code>.</li>
  <li><strong>Art Mode ikke støttet:</strong> Enkelte modeller/konfigurasjoner støtter ikke opplasting via Art API.</li>
  <li><strong>Bilde ser “feil beskåret” ut:</strong> Bruk 16:9-kilde (f.eks. 3840×2160) for et perfekt resultat.</li>
</ul>

<hr>

<h2>📄 Lisens</h2>
<p>LGPL-3.0</p>
