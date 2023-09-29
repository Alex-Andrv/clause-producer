library(tidyverse)
library(cowplot)

# TODO: setwd("PATH/TO/AAAI-24-Supplementary")

load_data <- function(prefix, inst) {
    df.orig <- read_csv(str_interp("${prefix}/${inst}/data_rho_original.csv"), show_col_types = FALSE)
    df.60s <- read_csv(str_interp("${prefix}/${inst}/data_rho_with-learnts_kissat310_60s_max10.csv"), show_col_types = FALSE)
    df.600s <- read_csv(str_interp("${prefix}/${inst}/data_rho_with-learnts_kissat310_600s_max10.csv"), show_col_types = FALSE)
    df.1200s <- read_csv(str_interp("${prefix}/${inst}/data_rho_with-learnts_kissat310_1200s_max10.csv"), show_col_types = FALSE)
    df.1800s <- read_csv(str_interp("${prefix}/${inst}/data_rho_with-learnts_kissat310_1800s_max10.csv"), show_col_types = FALSE)
    df.3600s <- read_csv(str_interp("${prefix}/${inst}/data_rho_with-learnts_kissat310_3600s_max10.csv"), show_col_types = FALSE)

    df <- bind_rows(
        "original" = df.orig,
        "60s" = df.60s,
        "600s" = df.600s,
        "1200s" = df.1200s,
        "1800s" = df.1800s,
        "3600s" = df.3600s,
        .id = "id",
    ) %>%
        mutate(id = as_factor(id)) %>%
        mutate(instance = inst)
}

plot_rho_learn <- function(prefix, inst) {
    df <- load_data(prefix, inst)
    df %>%
        filter(id %in% c("original", "600s", "1800s", "3600s")) %>%
        ggplot(aes(x = id, y = rho)) +
        geom_jitter(aes(color = id), width = 0.2, alpha = 0.5, size = 1) +
        geom_boxplot(aes(fill = id), outlier.shape = NA, alpha = 0.5) +
        guides(fill = "none", color = "none") +
        labs(x = NULL, y = "rho",
             # title = str_interp("${inst}")
        ) +
        theme_bw(base_size = 9)
}

save_plot_rho_learn <- function(prefix, inst) {
    p <- plot_rho_learn(prefix, inst)
    filename <- str_interp("plot_rho-learn_boxplots_${inst}")
    width <- 3
    height <- 1.5
    cat(str_interp("Saving '${filename}' with size ${width}x${height}\n"))
    ggsave(str_interp("${filename}.pdf"), p, width=width, height=height)
    ggsave(str_interp("${filename}.png"), p, dpi=300, width=width, height=height)
}

plot_rho_learn("experiments/rho-learn", "CvK-12")
save_plot_rho_learn("experiments/rho-learn", "CvK-12")
