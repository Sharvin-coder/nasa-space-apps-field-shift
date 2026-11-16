"""The Farm Sight world model: a proposed neurosymbolic architecture.

This module holds the text for the app's "The model" tab and MODEL.md. The
diagram is drawn by fieldshift/diagram.py.

STATUS matters: this is a design. It is not trained, and no result is claimed.
The prior-work entries were checked against their sources on 16 November 2026.
"""

NAME = "The Farm Sight world model"
TAGLINE = ("An action-conditioned world model of a single field, anchored to agronomic rules "
           "it is allowed to correct but not to break.")

STATUS = ("Proposed architecture. It is not trained yet, and no result is claimed for it. "
          "The rule program at its centre is the part already running in this app.")

SUMMARY = [
    "A world model learns how a system changes over time, so it can be run forward to ask "
    "what would happen under a choice nobody has made yet. Ours models one field. The "
    "choice is the crop planted each year; the forcing is the weather; the question is "
    "how the field responds over a whole rotation, including under a climate that has not "
    "happened.",
    "It is neurosymbolic: a learned model of field dynamics (neural) is tied to an explicit "
    "program of agronomic rules (symbolic). The rules are not a filter bolted on at the "
    "end. They sit inside the model as its starting point, its limits and its checker, and "
    "the network is confined to learning where, and by how much, the rules are wrong.",
]

# (number, name, kind, paragraphs)  kind: data | neural | symbolic | search | output
COMPONENTS = [
    ("1", "Observations on one grid", "data", [
        "Seven sources arrive at very different sharpness and tempo, from 30 m crop maps to "
        "50 km weather, and from daily to yearly. The harmonizer does not blur them onto a "
        "common pixel. It builds one sequence per field with a step of 16 days, and tags "
        "every value with the cell size and cadence it came from, so the model knows that a "
        "weather value is shared with the neighbours and a greenness value is not.",
        "Weather is aggregated within each step (totals, means and extremes), groundwater is "
        "interpolated between weekly maps, soil and terrain are repeated, and the yearly "
        "crop map becomes the action label for that season.",
    ]),
    ("2", "Encoders", "neural", [
        "Imagery is encoded by a frozen geospatial foundation model of the Prithvi-EO-2.0 "
        "class, pretrained by NASA and IBM on Harmonized Landsat and Sentinel-2 time "
        "series. Freezing it keeps the trainable part small enough for a team without a "
        "large compute budget. A light temporal network encodes weather and water, and an "
        "embedding encodes soil and terrain.",
    ]),
    ("3", "A two-clock latent state", "neural", [
        "The field's state is split in two. The fast state (canopy, root-zone water) "
        "advances every 16 days. The slow state (soil condition, water table, and the "
        "residue and nitrogen legacy of earlier crops) advances once a year.",
        "The split is what makes rotation planning possible. A single-season crop model "
        "forgets what was planted before; here the slow state is exactly the memory that "
        "carries one crop's effect into the next, which is what a rotation is.",
    ]),
    ("4", "Action-conditioned transition", "neural", [
        "The transition predicts the next state from the current state, the weather, and "
        "the crop in the ground. It is stochastic, so one rollout is one possible season "
        "and many rollouts give a distribution. It is trained in latent space in the JEPA "
        "style: the target is the encoding of what the satellites actually saw next, not "
        "the raw pixels, so the model does not spend capacity on cloud and sensor noise.",
        "Conditioning on the crop is the difference from existing Earth-observation world "
        "models, which forecast how vegetation responds to weather but have no notion of "
        "a decision.",
    ]),
    ("5", "Rule program", "symbolic", [
        "Published knowledge is written as an executable program. Crop tolerance ranges "
        "(FAO EcoCrop) become fuzzy predicates: 1 inside the optimal range, 0 outside the "
        "absolute range, linear between, combined by taking the minimum. Physical checks "
        "cover the water balance and whether the frost-free season is long enough. "
        "Conservation rules come from USDA NRCS Standard 328, plus the farmer's own limits.",
        "The program plays three roles. Anchor: the network does not predict a crop's fit; "
        "it predicts a correction to the rule-based fit. Mask: a crop outside its absolute "
        "range, or ruled out by the farmer, is never proposed. Verifier: every plan the "
        "planner returns is re-checked, and a plan that fails is rejected, not penalised.",
    ]),
    ("6", "Envelope-residual learning", "symbolic", [
        "The only learnable part of the rule program is a small offset on each corner of "
        "each crop's range, conditioned on region. The offset is bounded to a fraction of "
        "the range width and pushed toward zero, so it moves only where the satellite "
        "record insists.",
        "What comes out is not a set of hidden weights. It is a revised table: for example, "
        "that grain sorghum tolerates more rain in Iowa than the global table allows. An "
        "agronomist can read each correction, accept it or strike it out, and the accepted "
        "ones become the new rules.",
    ]),
    ("7", "Twin-field contrast", "neural", [
        "Crop choice is not random: farmers plant what suits their land, so a naive model "
        "would confuse a good field with a good crop. Neighbouring fields that share "
        "weather and soil but were planted differently are close to a natural experiment. "
        "The training loss includes the difference between such twins, so the model has "
        "to explain what changing the crop does, with the field held nearly fixed.",
    ]),
    ("8", "Verifier-guarded planner", "search", [
        "Candidate rotations are enumerated under the mask and rolled forward through "
        "every climate model in the NEX-GDDP-CMIP6 ensemble separately, and through "
        "replayed past years, instead of through one averaged future. Each rotation gets a "
        "distribution of outcomes, scored with the farmer's priorities on both the "
        "expected value and the bad tail (conditional value at risk), because a farmer "
        "survives the worst year, not the average one.",
        "Prediction intervals are calibrated on held-out years with conformal prediction, "
        "so a stated 80% range is tested against how often the truth actually fell inside.",
    ]),
]

# (label, expression, what it says)
EQUATIONS = [
    ("State", "s(t) = [ z_slow(y), z_fast(t) ]",
     "Slow and fast parts of one field's latent state."),
    ("Fast step", "z_fast(t+1) ~ p( · | z_fast(t), z_slow(y), w(t), a(y) )",
     "Every 16 days, given weather w and the crop a planted that year."),
    ("Slow step", "z_slow(y+1) = g( z_slow(y), Σ z_fast, a(y) )",
     "Once a year: the crop leaves its mark on the soil state."),
    ("Rule-anchored fit", "fit(c) = min_k μ( x_k ; e(c,k) + δ(r,c,k) ),   |δ| ≤ β · width",
     "EcoCrop envelope e for crop c and factor k, plus a bounded learned offset δ for "
     "region r."),
    ("Training loss", "L = L_latent + λ₁ L_obs + λ₂ L_water + λ₃ L_twin + λ₄ ‖δ‖₁",
     "Latent prediction, next-observation error, water-balance violation, twin-field "
     "contrast, and sparsity on the rule offsets."),
    ("Plan", "r* = argmax over verified r of  E_m[ U(r) ] − κ · CVaR_α[ −U(r) ]",
     "Best rotation over climate models m, trading average utility against the bad tail."),
]

# (title, authors and year, what it does, what the Farm Sight design adds, url)
PRIOR_WORK = [
    ("EO-WM: a physically informed world model for probabilistic Earth observation forecasting",
     "Luo et al., 2026",
     "A world model that forecasts satellite observations from weather.",
     "Weather is the only driver. There is no action, so it cannot compare what a farmer "
     "might plant, and it has no symbolic rules.",
     "https://arxiv.org/abs/2606.27277"),
    ("KGML-ag: knowledge-guided machine learning to simulate agroecosystems",
     "Liu et al., 2022",
     "Ties a recurrent network to a process-based ecosystem model to predict fluxes.",
     "The knowledge is process equations for one crop system. It predicts, but does not "
     "plan rotations, and its learned part is not a readable rule table.",
     "https://doi.org/10.5194/gmd-15-2839-2022"),
    ("NeuralCrop: combining physics and machine learning for improved crop modelling",
     "Lin et al., 2025",
     "A differentiable hybrid of the LPJmL crop model and neural components.",
     "Needs a full process model for every crop and flux-tower data to tune it. No "
     "decision layer.",
     "https://arxiv.org/abs/2512.20177"),
    ("Crop rotation optimization by combining model-based reinforcement learning with "
     "symbolic planning",
     "Wagner, 2024 (TU Wien thesis)",
     "A reinforcement-learning agent whose crop choices a symbolic planner restricts.",
     "Learns inside a hand-built simulator, not from observed field dynamics. Rules only "
     "restrict; they are not corrected by data.",
     "https://repositum.tuwien.at/handle/20.500.12708/197369"),
    ("AI- and data-driven crop rotation planning",
     "Fenz et al., 2023",
     "A deep Q-network that generates rotations from suitability matrices and NDVI.",
     "No learned model of how a field responds over time, and no uncertainty across "
     "climate futures.",
     "https://aminer.org/pub/6523b753939a5f40821c02bc/ai-and-data-driven-crop-rotation-planning"),
    ("Precrop payoffs: causal machine learning reveals large but variable yield benefits "
     "of crop rotation",
     "Kluger, Di Tommaso and Lobell, 2025",
     "Estimates the causal effect of the preceding crop from crop maps and satellites.",
     "Estimates effects after the fact. It is the evidence base for our twin-field "
     "contrast, not a simulator or a planner.",
     "https://arxiv.org/abs/2506.02384"),
    ("Prithvi-EO-2.0: a versatile multi-temporal foundation model for Earth observation",
     "Szwarcman et al., 2024",
     "NASA and IBM's foundation model pretrained on Harmonized Landsat Sentinel-2.",
     "A representation, not a dynamics model. We use this class of model as the frozen "
     "imagery encoder.",
     "https://arxiv.org/abs/2412.02732"),
]

BUILDING_BLOCKS = (
    "The latent-dynamics idea follows world models such as DreamerV3 (Hafner et al., 2023, "
    "https://arxiv.org/abs/2301.04104), and the fuzzy treatment of rules follows work on "
    "differentiable fuzzy logic (van Krieken, Acar and van Harmelen, 2020, "
    "https://arxiv.org/abs/2002.06100).")

CONTRIBUTIONS = [
    ("The crop is an action",
     "A satellite world model conditioned on the farmer's decision, so rotations can be "
     "simulated, not just weather responses forecast."),
    ("Envelope-residual learning",
     "Rules are differentiable fuzzy predicates whose ranges the data may shift within "
     "hard bounds. The learned result is a revised rule table a person can audit."),
    ("A two-clock state built for rotations",
     "A yearly slow state carries one crop's legacy into the next season, which a "
     "single-season model cannot represent."),
    ("Twin-field contrast",
     "Neighbouring fields with different crops supply a causal training signal, with "
     "labels that are free and public."),
    ("Verified, risk-aware planning",
     "Plans are searched under a symbolic mask, scored on the bad tail across separate "
     "climate models, and rejected outright if they break a rule."),
]

NOVELTY_CLAIM = (
    "We searched the literature on 16 November 2026 and found each ingredient on its own: "
    "weather-driven satellite world models, hybrid physics and machine-learning crop "
    "models, rotation planners with symbolic limits, and causal estimates of rotation "
    "effects. We did not find them combined into one action-conditioned world model whose "
    "symbolic rules are both its constraint and the thing it learns to correct. A short "
    "search cannot prove that nobody has done it, so we state this as what we found, not "
    "as a guarantee.")

# (step, text)
EVALUATION = [
    ("Training set",
     "Fields sampled across the Corn Belt and the Plains: ten years of crop planted, "
     "16-day greenness and weather, the same calls the app already makes for one pin."),
    ("Baselines it has to beat",
     "Repeating last year, the rule program alone, a network with no rules, and a "
     "weather-only world model with the crop input removed."),
    ("Held-out years and regions",
     "Tested on drought years and on states never seen in training, because that is the "
     "situation a farmer is actually in."),
    ("Ablations",
     "Remove the slow state, the twin-field term, and the offset bounds one at a time, to "
     "show which parts earn their place."),
    ("An outside check",
     "Compare against published county yields (USDA NASS), and have an agronomist review "
     "every envelope correction before any reaches a farmer."),
]

RISKS = [
    "Greenness is not yield and not profit. A model that predicts greenness well may still "
    "rank rotations badly for income.",
    "A 250 m pixel can straddle two fields and crop maps contain errors, so some labels "
    "will be wrong. Twin fields are similar, not identical.",
    "A learned correction could reflect irrigation or management instead of climate, and "
    "then would not transfer to a neighbouring farm.",
    "Ten years of history may not span the 2040 climate. That is where the rules, not the "
    "learned patterns, have to carry the weight, and why the offsets are bounded.",
]
