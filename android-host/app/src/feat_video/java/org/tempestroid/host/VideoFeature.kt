package org.tempestroid.host

import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import androidx.media3.common.MediaItem
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.ui.PlayerView

/**
 * REAL `video` feature renderer (built only when `-Ptempest.features` includes
 * `video`). A Media3 [ExoPlayer] hosted in a [PlayerView] via [AndroidView]. The
 * `src` is loaded as a [MediaItem]; `autoplay`/`controls`/`muted`/`loop` map to
 * the player + view. The player is released when the view leaves the composition.
 * The stub counterpart in `src/stub_video` has the identical signature.
 *
 * @param node the serialized `VideoPlayer` node.
 * @param style the resolved Compose style spec.
 */
@Composable
fun RenderVideoPlayer(node: TempestNode, style: Map<String, Any?>) {
    val context = LocalContext.current
    val src = node.props["src"] as? String ?: ""
    val autoplay = node.props["autoplay"] as? Boolean ?: false
    val loop = node.props["loop"] as? Boolean ?: false
    val controls = node.props["controls"] as? Boolean ?: true
    val muted = node.props["muted"] as? Boolean ?: false
    val player = remember(src) {
        ExoPlayer.Builder(context).build().apply {
            if (src.isNotEmpty()) setMediaItem(MediaItem.fromUri(src))
            repeatMode = if (loop) ExoPlayer.REPEAT_MODE_ONE else ExoPlayer.REPEAT_MODE_OFF
            volume = if (muted) 0f else 1f
            prepare()
            playWhenReady = autoplay
        }
    }
    DisposableEffect(player) {
        onDispose { player.release() }
    }
    AndroidView(
        modifier = baseModifier(style),
        factory = { ctx ->
            PlayerView(ctx).apply {
                this.player = player
                useController = controls
            }
        },
    )
}
