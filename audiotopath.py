from comfy_api.latest import io
import os
import torchaudio
import torch
import folder_paths


class AudioToPath(io.ComfyNode):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="AudioToPath",
            display_name="Audio to Path",     # UI 里的名称
            category="audio",
            inputs=[
                io.Audio.Input("audio"),
            ],
            outputs=[
                io.String.Output("audio_path"),
            ],
        )

    @classmethod
    def execute(cls, audio) -> io.NodeOutput:
        # audio dict:
        # { "waveform": Tensor, "sample_rate": int }
        waveform = audio["waveform"]
        sample_rate = audio["sample_rate"]

        # ensure CPU tensor
        waveform = waveform.detach().cpu()

        # unify to [C, T]
        if waveform.dim() == 3 and waveform.shape[0] == 1:
            waveform = waveform[0]
        elif waveform.dim() == 1:
            waveform = waveform.unsqueeze(0)

        # ---- Use ComfyUI default temp directory ----
        tmp_dir = folder_paths.get_temp_directory()

        os.makedirs(tmp_dir, exist_ok=True)
        tmp_path = os.path.join(tmp_dir, "audio_temp.wav")

        # If repeated calls are possible, prevent override collision
        idx = 1
        base = tmp_path
        while os.path.exists(tmp_path):
            tmp_path = base.replace(".wav", f"_{idx}.wav")
            idx += 1

        # save wav
        torchaudio.save(tmp_path, waveform, sample_rate)

        return io.NodeOutput(tmp_path)


NODE_CLASS_MAPPINGS = {
    "AudioToPath": AudioToPath,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AudioToPath": "Audio to Path",
}
