import cv2
import numpy as np
from PIL import Image
from loguru import logger
from scipy.signal.windows import gaussian
import torch

from comic_text_detector.inference import TextDetector
from manga_ocr import MangaOcr
from manga_ocr.ocr import post_process
from mokuro import __version__
from mokuro.cache import cache
from mokuro.utils import imread


class MangaPageOcr:
    def __init__(
        self,
        pretrained_model_name_or_path="kha-white/manga-ocr-base",
        force_cpu=False,
        detector_input_size=1024,
        text_height=64,
        max_ratio_vert=16,
        max_ratio_hor=8,
        anchor_window=2,
        disable_ocr=False,
        ocr_batch_size=16,
    ):
        self.text_height = text_height
        self.max_ratio_vert = max_ratio_vert
        self.max_ratio_hor = max_ratio_hor
        self.anchor_window = anchor_window
        self.disable_ocr = disable_ocr
        self.ocr_batch_size = ocr_batch_size

        if not self.disable_ocr:
            if not force_cpu and torch.cuda.is_available():
                self.device = "cuda"
            elif not force_cpu and torch.backends.mps.is_available():
                self.device = "mps"
            else:
                self.device = "cpu"
            logger.info(f"Initializing text detector, using device {self.device}")
            self.text_detector = TextDetector(
                model_path=cache.comic_text_detector, input_size=detector_input_size, device=self.device, act="leaky"
            )

            self.mocr = MangaOcr(pretrained_model_name_or_path, force_cpu)

    def _ocr_crops(self, pil_crops):
        if not pil_crops:
            return []

        results = []
        for i in range(0, len(pil_crops), self.ocr_batch_size):
            batch = pil_crops[i : i + self.ocr_batch_size]
            pixel_values = self.mocr.processor(batch, return_tensors="pt").pixel_values.to(self.mocr.model.device)
            with torch.inference_mode():
                tokens = self.mocr.model.generate(
                    pixel_values,
                    max_length=96,
                    num_beams=4,
                ).cpu()
                decoded = self.mocr.tokenizer.batch_decode(tokens, skip_special_tokens=True)
                results.extend([post_process(t) for t in decoded])
        return results

    def __call__(self, img_or_path):
        if isinstance(img_or_path, np.ndarray):
            img = img_or_path
        else:
            img = imread(img_or_path)

        H, W, *_ = img.shape
        result = {"version": __version__, "img_width": W, "img_height": H, "blocks": []}

        if self.disable_ocr:
            return result

        with torch.inference_mode():
            mask, mask_refined, blk_list = self.text_detector(img, refine_mode=1, keep_undetected_mask=True)

        all_crops = []
        crop_routes = []

        for blk_idx, blk in enumerate(blk_list):
            result_blk = {
                "box": list(blk.xyxy),
                "vertical": blk.vertical,
                "font_size": blk.font_size,
                "lines_coords": [],
                "lines": [],
            }

            max_ratio = self.max_ratio_vert if blk.vertical else self.max_ratio_hor

            for line_idx, line in enumerate(blk.lines_array()):
                line_crops, cut_points = self.split_into_chunks(
                    img,
                    mask_refined,
                    blk,
                    line_idx,
                    textheight=self.text_height,
                    max_ratio=max_ratio,
                    anchor_window=self.anchor_window,
                )

                result_blk["lines_coords"].append(line.tolist())
                result_blk["lines"].append("")

                for line_crop in line_crops:
                    if blk.vertical:
                        line_crop = cv2.rotate(line_crop, cv2.ROTATE_90_CLOCKWISE)
                    all_crops.append(Image.fromarray(line_crop).convert("L").convert("RGB"))
                    crop_routes.append((blk_idx, line_idx))

            result["blocks"].append(result_blk)

        if all_crops:
            ocr_texts = self._ocr_crops(all_crops)
            for (blk_idx, line_idx), text in zip(crop_routes, ocr_texts):
                result["blocks"][blk_idx]["lines"][line_idx] += text

        return result

    @staticmethod
    def split_into_chunks(img, mask_refined, blk, line_idx, textheight, max_ratio=16, anchor_window=2):
        line_crop = blk.get_transformed_region(img, line_idx, textheight)

        h, w, *_ = line_crop.shape
        ratio = w / h

        if ratio <= max_ratio:
            return [line_crop], []

        else:
            k = gaussian(textheight * 2, textheight / 8)

            line_mask = blk.get_transformed_region(mask_refined, line_idx, textheight)
            num_chunks = int(np.ceil(ratio / max_ratio))

            anchors = np.linspace(0, w, num_chunks + 1)[1:-1]

            line_density = line_mask.sum(axis=0)
            line_density = np.convolve(line_density, k, "same")
            line_density /= line_density.max()

            anchor_window *= textheight

            cut_points = []
            for anchor in anchors:
                anchor = int(anchor)

                n0 = np.clip(anchor - anchor_window // 2, 0, w)
                n1 = np.clip(anchor + anchor_window // 2, 0, w)

                p = line_density[n0:n1].argmin()
                p += n0

                cut_points.append(p)

            return np.split(line_crop, cut_points, axis=1), cut_points
