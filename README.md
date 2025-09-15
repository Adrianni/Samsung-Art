<h1>Frame Art Uploader 🖼️📺</h1>
<p>Upload art/photos to <strong>Samsung The Frame</strong> from the command line. Supports either a local image file, a random <em>Bing Wallpaper</em>, or a landscape photo from <em>Unsplash</em> (random or specific). The script automatically crops/resizes to 3840×2160 (4K) before uploading and remembers previously uploaded images in <code>uploaded_files.json</code>.</p>

<hr>

<h2>🔧 Prerequisites</h2>
<ul>
  <li>Python 3.9+</li>
  <li>The TV and computer on the same network</li>
  <li>The TV must support and (ideally) be in <em>Art Mode</em></li>
  <li>Unsplash API access key (only if you use <code>--unsplash [IMAGE_ID]</code>)</li>
</ul>

<h2>📦 Installation</h2>
<pre><code># Optional but recommended virtual environment
python3 -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
</code></pre>

<hr>

<h2>▶️ Usage</h2>
<p>Run the script with <code>--tvip</code> and <em>one</em> of the sources <code>--bingwallpaper</code>, <code>--unsplash [IMAGE_ID]</code>, or <code>--image &lt;path&gt;</code>.</p>

<p>For <code>--unsplash [IMAGE_ID]</code> you need an <em>Unsplash API access key</em>. Set it in the <code>UNSPLASH_ACCESS_KEY</code> environment variable or directly in <code>frame_art_uploader.py</code>.</p>

<h3>Examples</h3>
<pre><code><h3>1) Use a random Bing wallpaper on one TV</h3>
python3 frame_art_uploader.py --tvip 192.168.1.20 --bingwallpaper

<h3>2) Upload a local image file</h3>
python3 frame_art_uploader.py --tvip 192.168.1.20 --image /path/to/image.jpg

<h3>3) Use a random Unsplash landscape</h3>
# assumes UNSPLASH_ACCESS_KEY is set
export UNSPLASH_ACCESS_KEY=your_key
python3 frame_art_uploader.py --tvip 192.168.1.20 --unsplash

<h3>4) Use a specific Unsplash image by ID</h3>
python3 frame_art_uploader.py --tvip 192.168.1.20 --unsplash a-body-of-water-surrounded-by-trees-on-a-sunny-day-Pyk2RVJ5fVY

<h3>5) Multiple TVs (comma-separated list)</h3>
python3 frame_art_uploader.py --tvip 192.168.1.20,192.168.1.21 --bingwallpaper

<h3>6) Debug (more logging)</h3>
python3 frame_art_uploader.py --tvip 192.168.1.20 --bingwallpaper --debug
</code></pre>

<hr>

<h2>⚙️ Arguments</h2>
<table>
  <thead>
    <tr>
      <th>Flag</th>
      <th>Required</th>
      <th>Description</th>
      <th>Example</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><code>--tvip</code></td>
      <td>Yes</td>
      <td>IP for one or more TVs (comma separated)</td>
      <td><code>--tvip 192.168.1.20,192.168.1.21</code></td>
    </tr>
    <tr>
      <td><code>--bingwallpaper</code></td>
      <td>Yes* (either/or)</td>
      <td>Use a random Bing Wallpaper (downloaded via HTTP)</td>
      <td><code>--bingwallpaper</code></td>
    </tr>
    <tr>
      <td><code>--unsplash [IMAGE_ID]</code></td>
      <td>Yes* (either/or)</td>
      <td>Use an Unsplash photo. Provide IMAGE_ID for a specific photo or omit it for a random landscape (requires UNSPLASH_ACCESS_KEY)</td>
      <td><code>--unsplash</code> or <code>--unsplash a-body-of-water-surrounded-by-trees-on-a-sunny-day-Pyk2RVJ5fVY</code></td>
    </tr>
    <tr>
      <td><code>--image &lt;path&gt;</code></td>
      <td>Yes* (either/or)</td>
      <td>Use a local image file</td>
      <td><code>--image /path/to/image.jpg</code></td>
    </tr>
    <tr>
      <td><code>--debug</code></td>
      <td>No</td>
      <td>Enable more detailed logging (useful for troubleshooting)</td>
      <td><code>--debug</code></td>
    </tr>
  </tbody>
</table>

<hr>

<h2>🖼️ Image preparation</h2>
<ul>
  <li>Images are automatically scaled and center-cropped to <strong>3840×2160</strong> (JPEG, quality 90).</li>
  <li>Portrait/square compositions are cropped on the sides to fit 16:9 (The Frame).</li>
</ul>

<hr>

<h2>🧠 Upload reuse</h2>
<p>The script stores metadata in <code>uploaded_files.json</code> so it can reuse previously uploaded images (per source, and per TV when multiple TVs are used).</p>

<hr>

<h2>🧯 Troubleshooting</h2>
<ul>
  <li><strong>No connection:</strong> Verify the IP (<code>ping</code>), ensure the TV and computer are on the same VLAN/subnet, and try <code>--debug</code>.</li>
  <li><strong>Art Mode not supported:</strong> Some models/configurations do not support uploads via the Art API.</li>
  <li><strong>Image looks “incorrectly cropped”:</strong> Use a 16:9 source (e.g., 3840×2160) for perfect framing.</li>
</ul>

<hr>

<h2>📄 License</h2>
<p>LGPL-3.0</p>
