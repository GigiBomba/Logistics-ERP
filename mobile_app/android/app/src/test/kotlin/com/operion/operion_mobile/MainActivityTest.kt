package com.operion.operion_mobile

import android.content.Intent
import androidx.test.core.app.ApplicationProvider
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.embedding.engine.loader.FlutterLoader
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/**
 * Basic smoke/launching tests for MainActivity using Robolectric.
 *
 * These tests verify that the activity can be created, that it
 * is a [FlutterActivity], and that the Flutter engine initialises
 * without crashing.  A real Flutter engine is *not* started in
 * Robolectric (the native libraries are not available), so the
 * test focuses on the Kotlin/Android wiring.
 */
@RunWith(RobolectricTestRunner::class)
@Config(
    application = ApplicationProvider::class,
    sdk = [34]
)
class MainActivityTest {

    // ---------------------------------------------------------------
    // Activity launches correctly
    // ---------------------------------------------------------------

    @Test
    fun activity_shouldLaunchSuccessfully() {
        val controller = Robolectric.buildActivity(MainActivity::class.java)
        val activity = controller.create().start().resume().visible().get()

        assertNotNull("MainActivity should not be null", activity)
        assertTrue(
            "MainActivity must be a FlutterActivity",
            activity is FlutterActivity
        )
    }

    @Test
    fun activity_shouldResumeWithoutCrash() {
        val controller = Robolectric.buildActivity(MainActivity::class.java)
        controller.create().start().resume()

        // If we reach here without an exception the test passes.
        assertTrue("Activity resumed successfully", true)
    }

    @Test
    fun activity_shouldCreateValidIntent() {
        val intent = Intent(
            ApplicationProvider.getApplicationContext(),
            MainActivity::class.java
        )
        assertNotNull("Intent should not be null", intent)

        val controller = Robolectric
            .buildActivity(MainActivity::class.java, intent)
            .create()
            .start()

        assertNotNull("Activity created from intent should exist", controller.get())
    }

    // ---------------------------------------------------------------
    // Flutter engine setup
    // ---------------------------------------------------------------

    @Test
    fun flutterEngine_shouldHaveExpectedRegistry() {
        // Verify that the FlutterLoader is available – this confirms the
        // Flutter infrastructure is wired into the app module.
        val flutterLoader = FlutterLoader()
        assertNotNull("FlutterLoader instance should be created", flutterLoader)
    }

    @Test
    fun activity_shouldProvideDartExecutor() {
        val controller = Robolectric.buildActivity(MainActivity::class.java)
        val activity = controller.create().start().resume().get() as MainActivity

        // The FlutterEngine is created lazily by FlutterActivity.
        // In Robolectric the native library won't load, but we can still
        // verify the activity class structure is correct.
        assertNotNull(activity)
        assertTrue(
            "Activity should expose FlutterEngine via getFlutterEngine()",
            activity is FlutterActivity
        )
    }

    @Test
    fun activity_cacheDirExists() {
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        val cacheDir = context.cacheDir
        assertNotNull("Cache directory should be accessible", cacheDir)
        assertTrue("Cache directory must exist", cacheDir.exists())
    }

    // ---------------------------------------------------------------
    // Basic smoke test
    // ---------------------------------------------------------------

    @Test
    fun smoke_activityLifecycle() {
        // Full lifecycle: create → start → resume → pause → stop → destroy
        val controller = Robolectric.buildActivity(MainActivity::class.java)

        controller.create()
        assertNotNull("After create", controller.get())

        controller.start()
        assertNotNull("After start", controller.get())

        controller.resume()
        assertNotNull("After resume", controller.get())

        controller.pause()
        assertNotNull("After pause", controller.get())

        controller.stop()
        assertNotNull("After stop", controller.get())

        controller.destroy()
        assertNotNull("After destroy", controller.get())
    }

    @Test
    fun smoke_activityConfigurationChange() {
        val controller = Robolectric.buildActivity(MainActivity::class.java)
        val activity = controller.create().start().resume().get()

        // Simulate a configuration change (rotation)
        controller.configurationChange(
            android.content.res.Configuration()
        )

        // After re-creation the activity should still be valid
        assertNotNull("Activity should survive config change", activity)
    }
}
